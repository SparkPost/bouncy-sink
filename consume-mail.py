#!/usr/bin/env python3
# Consume mail received from PowerMTA
# command-line params may also be present, as per PMTA Users Guide "3.3.12 Pipe Delivery Directives"
#
# Author: Steve Tuck.  (c) 2018 SparkPost
#
# Pre-requisites:
#   pip3 install requests, dnspython
#
import logging, sys, os, email, time, glob, requests, dns.resolver, smtplib
from html.parser import HTMLParser

# workaround as per https://stackoverflow.com/questions/45124127/unable-to-extract-the-body-of-the-email-file-in-python
from email import policy

# Parse html email body, looking for open-pixel and links.  Follow these to do open & click tracking
class MyHTMLParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            for attr in attrs:
                if attr[0] == 'src':
                    url = attr[1]
                    r = requests.get(url)
        if tag == 'a':
            for attr in attrs:
                if attr[0] == 'href':
                    url = attr[1]
                    r = requests.get(url)

def openAndClick(mail):
    htmlParser = MyHTMLParser()
    htmlParser.feed(mail.get_body('text/html').as_string())  # Open & click processing

ArfFormat = '''From: <{fblFrom}>
Date: Mon, 02 Jan 2006 15:04:05 MST
Subject: FW: Earn money
To: <{fblTo}>
MIME-Version: 1.0
Content-Type: multipart/report; report-type=feedback-report;
      boundary="{boundary}"

--{boundary}
Content-Type: text/plain; charset="US-ASCII"
Content-Transfer-Encoding: 7bit

This is an email abuse report for an email message
received from IP 10.67.41.167 on Thu, 8 Mar 2005
14:00:00 EDT.
For more information about this format please see
http://www.mipassoc.org/arf/.

--{boundary}
Content-Type: message/feedback-report

Feedback-Type: abuse
User-Agent: SomeGenerator/1.0
Version: 0.1

--{boundary}
Content-Type: message/rfc822
Content-Disposition: inline

From: <{returnPath}>
Received: from mailserver.example.net (mailserver.example.net
        [10.67.41.167])
        by example.com with ESMTP id M63d4137594e46;
        Thu, 08 Mar 2005 14:00:00 -0400
To: <Undisclosed Recipients>
Subject: Earn money
MIME-Version: 1.0
Content-type: text/plain
Message-ID: 8787KJKJ3K4J3K4J3K4J3.mail@{domain}
X-MSFBL: {msfbl}
Date: Thu, 02 Sep 2004 12:31:03 -0500

Spam Spam Spam
Spam Spam Spam
Spam Spam Spam
Spam Spam Spam

--{boundary}--
'''
def buildArf(fblFrom, fblTo, msfbl, returnPath):
    boundary = '_----{0:d}===_61/00-25439-267B0055'.format(int(time.time()))
    domain = fblFrom.split('@')[1]
    msg = ArfFormat.format(fblFrom=fblFrom, fblTo=fblTo, boundary=boundary, returnPath=returnPath, domain=domain, msfbl=msfbl)
    return msg

OobFormat = '''From: {oobFrom}
Date: Mon, 02 Jan 2006 15:04:05 MST
Subject: Returned mail: see transcript for details
Auto-Submitted: auto-generated (failure)
To: {oobTo}
Content-Type: multipart/report; report-type=delivery-status;
	boundary="{boundary}"

This is a MIME-encapsulated message

--{boundary}

The original message was received at Mon, 02 Jan 2006 15:04:05 -0700
from example.com.sink.sparkpostmail.com [52.41.116.105]

   ----- The following addresses had permanent fatal errors -----
<{oobTo}>
    (reason: 550 5.0.0 <{oobTo}>... User unknown)

   ----- Transcript of session follows -----
... while talking to {toDomain}:
>>> DATA
<<< 550 5.0.0 <{oobTo}>... User unknown
550 5.1.1 <{oobTo}>... User unknown
<<< 503 5.0.0 Need RCPT (recipient)

--{boundary}
Content-Type: message/delivery-status

Reporting-MTA: dns; {toDomain}
Received-From-MTA: DNS; {fromDomain}
Arrival-Date: Mon, 02 Jan 2006 15:04:05 MST

Final-Recipient: RFC822; {oobTo}
Action: failed
Status: 5.0.0
Remote-MTA: DNS; {toDomain}
Diagnostic-Code: SMTP; 550 5.0.0 <{oobTo}>... User unknown
Last-Attempt-Date: Mon, 02 Jan 2006 15:04:05 MST

--{boundary}
Content-Type: message/rfc822

{rawMsg}

--{boundary}--
'''
def buildOob(oobFrom, oobTo, rawMsg):
    boundary = '_----{0:d}===_61/00-25439-267B0055'.format(int(time.time()))
    fromDomain = oobFrom.split('@')[1]
    toDomain = oobTo.split('@')[1]
    msg = OobFormat.format(oobFrom=oobFrom, oobTo=oobTo, boundary=boundary, toDomain=toDomain, fromDomain=fromDomain, rawMsg=rawMsg)
    return msg

#
# Avoid creating backscatter spam https://en.wikipedia.org/wiki/Backscatter_(email). Check that returnPath points to SparkPost.
# If valid, returns the MX and the associated To: addr for FBLs.
#
def mapRP_MXtoSparkPostFbl(returnPath):
    rpDomainPart = returnPath.split('@')[1]
    try:
        mxList = dns.resolver.query(rpDomainPart, 'MX')             # Will throw exception if not found
        if mxList:
            mx = mxList[0].to_text().split()[1][:-1]                # Take first one in the list, remove the priority field and trailing '.'
            if mx.endswith('smtp.sparkpostmail.com'):               # SparkPost US
                fblTo = 'fbl@sparkpostmail.com'
            elif mx.endswith('e.sparkpost.com'):                    # SparkPost Enterprise
                tenant = mx.split('.')[0]
                fblTo = 'fbl@' + tenant + '.mail.e.sparkpost.com'
            elif mx.endswith('smtp.eu.sparkpostmail.com'):          # SparkPost EU
                fblTo = 'fbl@eu.sparkpostmail.com'
            else:
                return None
            return mx, fblTo                                        # Valid
        else:
            return None
    except dns.exception.DNSException as err:
        return None

#
# Generate and deliver an FBL response (to cause a spam_complaint event in SparkPost)
# Based on https://github.com/SparkPost/gosparkpost/tree/master/cmd/fblgen
#
def fblGen(mail):
    returnPath = mail['Return-Path'].lstrip('<').rstrip('>')        # Remove < > brackets from address
    fblFrom = mail['to']
    mx, fblTo = mapRP_MXtoSparkPostFbl(returnPath)
    if mx:
        arfMsg = buildArf(fblFrom, fblTo, mail['X-MSFBL'], returnPath)
        try:
            # Deliver an FBL to SparkPost using SMTP direct, so that we can check the response code.
            with smtplib.SMTP(mx) as smtpObj:
                smtpObj.sendmail(fblFrom, fblTo, arfMsg)            # if no exception, the mail is sent (250OK)
                return 'FBL sent to ' + fblTo + ' via ' + mx

        except smtplib.SMTPException as err:
            return '!FBL endpoint returned SMTP error: ' + str(err)
    else:
        return '!FBL not sent, Return-Path not recognized as SparkPost'

#
# Generate and deliver an OOB response (to cause a out_of_band event in SparkPost)
# Based on https://github.com/SparkPost/gosparkpost/tree/master/cmd/oobgen
#
def oobGen(mail):
    returnPath = mail['Return-Path'].lstrip('<').rstrip('>')        # Remove < > brackets from address
    mx, _ = mapRP_MXtoSparkPostFbl(returnPath)
    if mx:
        # from/to are opposite here, since we're simulating a reply
        oobTo = returnPath
        oobFrom = str(mail['From'])
        oobMsg = buildOob(oobTo, oobFrom, mail)
        try:
            # Deliver an OOB to SparkPost using SMTP direct, so that we can check the response code.
            with smtplib.SMTP(mx) as smtpObj:
                smtpObj.sendmail(oobFrom, oobTo, oobMsg)            # if no exception, the mail is sent (250OK)
                return 'OOB sent to ' + oobTo + ' via ' + mx

        except smtplib.SMTPException as err:
            return '!OOB endpoint returned SMTP error: ' + str(err)
    else:
        return '!OOB not sent, Return-Path not recognized as SparkPost'

def processMail(mail, logger):
    openAndClick(mail)
    resFbl = fblGen(mail)
    resOob = oobGen(mail)
    logger.info(mail['to'] + ',' + mail['from'] + ',' + resFbl + ',' + resOob)

# -----------------------------------------------------------------------------------------
# Main code
# -----------------------------------------------------------------------------------------
# Take mail input depending on command-line options:
# -f        file        (single file)
# -d        directory   (read process and delete any file with extension .msg)
# (blank)   stdin       (e.g. for pipe input)
startTime = time.time()                                             # measure run time

# Log some info on mail that is processed
logger = logging.getLogger('consume-mail')
logger.setLevel(logging.INFO)
fh = logging.FileHandler('consume-mail.log')
formatter = logging.Formatter('%(asctime)s,%(name)s,%(thread)d,%(levelname)s,%(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

params = ' '.join(sys.argv[1:])
logger.info('** Starting. Params='+params)

if len(sys.argv) > 2:
    if sys.argv[1] == '-f':
        with open(sys.argv[2]) as fIn:
            processMail(email.message_from_file(fIn, policy=policy.default), logger)
    elif sys.argv[1] == '-d':
        dir = sys.argv[2].rstrip('/')                               # strip trailing / if present
        for fname in glob.glob(os.path.join(dir, '*.msg')):
            if os.path.isfile(fname):
                with open(fname, 'r') as fIn:
                    msg = email.message_from_file(fIn, policy=policy.default)
                    processMail(msg, logger)
    else:
        processMail(email.message_from_file(sys.stdin, policy=policy.default), logger)

endTime = time.time()
execTime = str.format('{:.3f}', endTime-startTime)
logger.info('** Finishing. run time (sec)='+execTime)