#!/usr/bin/env python3
# Consume mail received from PowerMTA
# command-line params may also be present, as per PMTA Users Guide "3.3.12 Pipe Delivery Directives"
#
# Author: Steve Tuck.  (c) 2018 SparkPost
#
# Pre-requisites:
#   pip3 install requests, dnspython
#
import os, email, time, glob, requests, dns.resolver, smtplib, configparser, random, argparse, csv
import threading, queue

from html.parser import HTMLParser
# workaround as per https://stackoverflow.com/questions/45124127/unable-to-extract-the-body-of-the-email-file-in-python
from email import policy
from webReporter import Results, timeStr
from urllib.parse import urlparse
from datetime import datetime
from bouncerate import nWeeklyCycle
from common import readConfig, configFileName, createLogger, baseProgName, xstr


# -----------------------------------------------------------------------------
# FBL and OOB handling
# -----------------------------------------------------------------------------
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

# Avoid creating backscatter spam https://en.wikipedia.org/wiki/Backscatter_(email). Check that returnPath points to SparkPost.
# If valid, returns the MX and the associated To: addr for FBLs.
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
            elif mx.endswith('trymsys.net'):                        # SparkPost CST demo server domains
                fblTo = 'fbl@fbl.' + rpDomainPart
            else:
                return None, None
            return mx, fblTo                                        # Valid
        else:
            return None, None
    except dns.exception.DNSException as err:
        return None, None


# Generate and deliver an FBL response (to cause a spam_complaint event in SparkPost)
# Based on https://github.com/SparkPost/gosparkpost/tree/master/cmd/fblgen
#
def fblGen(mail, shareRes):
    returnPath = addressPart(mail['Return-Path'])
    if not returnPath:
        shareRes.incrementKey('fbl_missing_return_path')
        return '!Missing Return-Path:'
    elif not mail['to']:
        shareRes.incrementKey('fbl_missing_to')
        return '!Missing To:'
    else:
        fblFrom = addressPart(mail['to'])
        mx, fblTo = mapRP_MXtoSparkPostFbl(returnPath)
        if not mx:
            shareRes.incrementKey('fbl_return_path_not_sparkpost')
            return '!FBL not sent, Return-Path not recognized as SparkPost'
        else:
            arfMsg = buildArf(fblFrom, fblTo, mail['X-MSFBL'], returnPath)
            try:
                # Deliver an FBL to SparkPost using SMTP direct, so that we can check the response code.
                with smtplib.SMTP(mx) as smtpObj:
                    smtpObj.sendmail(fblFrom, fblTo, arfMsg)        # if no exception, the mail is sent (250OK)
                    shareRes.incrementKey('fbl_sent')
                    return 'FBL sent,to ' + fblTo + ' via ' + mx
            except smtplib.SMTPException as err:
                shareRes.incrementKey('fbl_smtp_error')
                return '!FBL endpoint returned SMTP error: ' + str(err)


# Generate and deliver an OOB response (to cause a out_of_band event in SparkPost)
# Based on https://github.com/SparkPost/gosparkpost/tree/master/cmd/oobgen
def oobGen(mail, shareRes):
    returnPath = addressPart(mail)
    if not returnPath:
        shareRes.incrementKey('oob_missing_return_path')
        return '!Missing Return-Path:'
    elif not mail['to']:
        shareRes.incrementKey('oob_missing_to')
        return '!Missing To:'
    else:
        mx, _ = mapRP_MXtoSparkPostFbl(returnPath)
        if not mx:
            shareRes.incrementKey('oob_return_path_not_sparkpost')
            return '!OOB not sent, Return-Path not recognized as SparkPost'
        else:
            # OOB is addressed back to the Return-Path: address, from the inbound To: address (i.e. the sink)
            oobTo = returnPath
            oobFrom = addressPart(mail['To'])
            oobMsg = buildOob(oobFrom, oobTo, mail)
            try:
                # Deliver an OOB to SparkPost using SMTP direct, so that we can check the response code.
                with smtplib.SMTP(mx) as smtpObj:
                    smtpObj.sendmail(oobFrom, oobTo, oobMsg)            # if no exception, the mail is sent (250OK)
                    shareRes.incrementKey('oob_sent')
                    return 'OOB sent,from {} to {} via {}'.format(oobFrom, oobTo, mx)
            except smtplib.SMTPException as err:
                shareRes.incrementKey('oob_smtp_error')
                return '!OOB endpoint returned SMTP error: ' + str(err)


# -----------------------------------------------------------------------------
# Open and Click handling
# -----------------------------------------------------------------------------

# Heuristic for whether this is really SparkPost: it rejects the OPTIONS verb but identifies itself in Server header
def isSparkPostTrackingEndpoint(s, url, shareRes, openClickTimeout):
    scheme, netloc, _, _, _, _ = urlparse(url)
    baseurl = scheme + '://' + netloc
    # optimisation - check if we already know this is SparkPost or not
    known = shareRes.getKey(baseurl)
    if known:
        known_bool = (known == b'1')
        return known_bool                                   # response is Bytestr, compare back to a Boolean
    else:
        r = s.options(url, allow_redirects=False, timeout=openClickTimeout)
        isSparky = (r.status_code == 405 and 'Server' in r.headers and r.headers['Server'] == 'msys-http') or \
            (r.status_code == 405 and 'X-MSYS' in r.headers and r.headers['X-MSYS'] == 'Signals SMTP Traffic Generator Tracking Endpoint')
        # NOTE redis-py now needs data passed in simple type such as int (will get converted to bytestr)
        isB = str(int(isSparky)).encode('utf-8')
        ok = shareRes.setKey(baseurl, isB, ex=3600)         # mark this as known, but with an expiry time
        return isSparky

# Improved "GET" - doesn't follow the redirect, and opens as stream (so doesn't actually fetch a lot of stuff)
def touchEndPoint(s, url, openClickTimeout, userAgent):
    r = s.get(url, allow_redirects=False, timeout=openClickTimeout, stream=True, headers={'User-Agent': userAgent})

# Parse html email body, looking for open-pixel and links.  Follow these to do open & click tracking
class MyHTMLOpenParser(HTMLParser):
    def __init__(self, s, shareRes, openClickTimeout, userAgent):
        HTMLParser.__init__(self)
        self.requestSession = s                             # Use persistent 'requests' session for speed
        self.shareRes = shareRes                            # shared results handle
        self.openClickTimeout = openClickTimeout
        self.userAgent = userAgent

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            for attrName, attrValue in attrs:
                if attrName == 'src':
                    # attrValue = url
                    if isSparkPostTrackingEndpoint(self.requestSession, attrValue, self.shareRes, self.openClickTimeout):
                        touchEndPoint(self.requestSession, attrValue, self.openClickTimeout, self.userAgent)
                    else:
                        self.shareRes.incrementKey('open_url_not_sparkpost')

class MyHTMLClickParser(HTMLParser):
    def __init__(self, s, shareRes, openClickTimeout, userAgent):
        HTMLParser.__init__(self)
        self.requestSession = s                             # Use persistent 'requests' session for speed
        self.shareRes = shareRes                            # shared results handle
        self.openClickTimeout = openClickTimeout
        self.userAgent = userAgent

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attrName, attrValue in attrs:
                if attrName == 'href':
                    # attrValue = url
                    if isSparkPostTrackingEndpoint(self.requestSession, attrValue, self.shareRes, self.openClickTimeout):
                        touchEndPoint(self.requestSession, attrValue, self.openClickTimeout, self.userAgent)
                    else:
                        self.shareRes.incrementKey('click_url_not_sparkpost')

# open / open again / click / click again logic, as per conditional probabilities
# takes a persistent requests session object
def openClickMail(mail, probs, shareRes, s, openClickTimeout, userAgent):
    ll = ''
    bd = mail.get_body('text/html')
    if bd:  # if no body to parse, ignore
        body = bd.get_content()                             # this handles quoted-printable type for us
        htmlOpenParser = MyHTMLOpenParser(s, shareRes, openClickTimeout, userAgent)
        ll += 'Open'
        shareRes.incrementKey('open')
        htmlOpenParser.feed(body)
        if random.random() <= probs['OpenAgain_Given_Open']:
            htmlOpenParser.feed(body)
            ll += '_OpenAgain'
            shareRes.incrementKey('open_again')
        if random.random() <= probs['Click_Given_Open']:
            htmlClickParser = MyHTMLClickParser(s, shareRes, openClickTimeout, userAgent)
            htmlClickParser.feed(body)
            ll += '_Click'
            shareRes.incrementKey('click')
            if random.random() <= probs['ClickAgain_Given_Click']:
                htmlClickParser.feed(body)
                ll += '_ClickAgain'
                shareRes.incrementKey('click_again')
    return ll


def addressSplit(e):
    """
    :param e: email.header
    :return: displayName, localpart, domainpart str
    """
    s = str(e)
    displayName = ''
    openB = s.find('<')
    closeB = s.find('>')
    if openB >= 0 and closeB >= 0:
        displayName = s[:openB].strip(' ')
        s = s[openB+1:closeB].strip(' ')        # this is the address part
    localpart, domainpart = s.split('@')
    return displayName, localpart, domainpart


def addressPart(e):
    """
    :param e: email.header
    :return: str Just the local@domain part
    """
    _, localPart, domainPart = addressSplit(e)
    return localPart + '@' + domainPart


# -----------------------------------------------------------------------------
# Process a single mail file according to the probabilistic model & special subdomains
# If special subdomains used, these override the model, providing SPF check has passed.
# Actions taken are recorded in a string which is passed back for logging, via clumsy
# For efficiency, takes a pre-allocated http requests session for opens/clicks, and can be multi-threaded
# Now opens, parses and deletes the file here inside the sub-process
# -----------------------------------------------------------------------------

def processMail(fname, probs, shareRes, resQ, session, openClickTimeout, userAgents, signalsTrafficPrefix, signalsOpenDays, doneMsgFileDest):
    try:
        with open(fname) as fIn:
            if doneMsgFileDest:
                if not os.path.isdir(doneMsgFileDest):
                    os.mkdir(doneMsgFileDest)
                donePathFile = os.path.join(doneMsgFileDest, os.path.basename(fname))
                os.rename(fname, donePathFile)
            else:
                os.remove(fname)  # OK to remove while open, contents destroyed once file handle closed
            mail = email.message_from_file(fIn, policy=policy.default)
            # Log addresses. Some rogue / spammy messages seen are missing From and To addresses
            logline = fname + ',' + xstr(mail['to']) + ',' + xstr(mail['from'])
            shareRes.incrementKey('total_messages')
            ts_min_resolution = int(time.time()//60)*60
            shareRes.incrementTimeSeries(str(ts_min_resolution))
            # Test that message was checked by PMTA and has valid DKIM signature
            auth = mail['Authentication-Results']
            if auth != None and 'dkim=pass' in auth:
                # Check for special "To" subdomains that signal what action to take (for safety, these also require inbound spf to have passed)
                subd = mail['to'].split('@')[1].split('.')[0]

                # SparkPost Signals engagement-recency adjustments
                doIt = True
                _, localpart, _ = addressSplit(mail['To'])
                alphaPrefix = localpart.split('+')[0]
                finalChar = localpart[-1]                           # final char should be a digit 0-9
                if alphaPrefix == signalsTrafficPrefix and str.isdigit(finalChar):
                    currentDay = datetime.now().day                 # 1 - 31
                    finalDigit = int(finalChar)
                    doIt = currentDay in signalsOpenDays[finalDigit]
                    logline += ',currentDay={},finalDigit={}'.format(currentDay, finalDigit)

                if subd == 'oob':
                    if 'spf=pass' in auth:
                        logline += ',' + oobGen(mail, shareRes)
                    else:
                        logline += ',!Special ' + subd + ' failed SPF check'
                        shareRes.incrementKey('fail_spf')
                elif subd == 'fbl':
                    if 'spf=pass' in auth:
                        logline += ',' + fblGen(mail, shareRes)
                    else:
                        logline += ',!Special ' + subd + ' failed SPF check'
                        shareRes.incrementKey('fail_spf')
                elif subd == 'openclick':
                    # doesn't need SPF pass
                    logline += ',' + openClickMail(mail, probs, shareRes, session, openClickTimeout, random.choice(userAgents))
                elif subd == 'accept':
                    logline += ',Accept'
                    shareRes.incrementKey('accept')
                else:
                    # Apply probabilistic model to all other domains
                    if random.random() <= probs['OOB']:
                        # Mail that out-of-band bounces would not not make it to the inbox, so would not get opened, clicked or FBLd
                        logline += ',' + oobGen(mail, shareRes)
                    elif random.random() <= probs['FBL']:
                        logline += ',' + fblGen(mail, shareRes)
                    elif random.random() <= probs['Open'] and doIt:
                        logline += ',' + openClickMail(mail, probs, shareRes, session, openClickTimeout, random.choice(userAgents))
                    else:
                        logline += ',Accept'
                        shareRes.incrementKey('accept')
            else:
                logline += ',!DKIM fail:' + xstr(auth)
                shareRes.incrementKey('fail_dkim')

    except Exception as err:
        logline += ',!Exception: '+ str(err)

    finally:
        resQ.put(logline)


# -----------------------------------------------------------------------------
# Consume emails using threads/processes
# -----------------------------------------------------------------------------

# start to consume files - set up logging, record start time (if first run)
def startConsumeFiles(logger, cfg, fLen):
    startTime = time.time()                                         # measure run time
    shareRes = Results()                                            # class for sharing summary results
    k = 'startedRunning'
    res = shareRes.getKey(k)                                        # read back results from previous run (if any)
    if not res:
        st = timeStr(startTime)
        ok = shareRes.setKey(k, st)
        logger.info('** First run - set {} = {}, ok = {}'.format(k, st, ok))
    maxThreads = cfg.getint('Max_Threads', 16)
    logger.info('** Process starting: consuming {} mail file(s) with {} threads'.format(fLen, maxThreads))
    return shareRes, startTime, maxThreads

def stopConsumeFiles(logger, shareRes, startTime, countDone):
    endTime = time.time()
    runTime = endTime - startTime
    runRate = (0 if runTime == 0 else countDone / runTime)          # Ensure no divide by zero
    logger.info('** Process finishing: run time(s)={:.3f},done {},done rate={:.3f}/s'.format(runTime, countDone, runRate))
    history = 10 * 24 * 60 * 60                                     # keep this much time-series history (seconds)
    shareRes.delTimeSeriesOlderThan(int(startTime) - history)


# return arrays of resources per thread
def initThreads(maxThreads):
    th = [None] * maxThreads
    thSession = [None] * maxThreads
    for i in range(maxThreads):
        thSession[i] = requests.session()
    return th, thSession

# search for a free slot, with memory (so acts as round-robin)
def findFreeThreadSlot(th, thIdx):
    t = (thIdx+1) % len(th)
    while True:
        if th[t] == None:                       # empty slot
            return t
        elif not th[t].is_alive():              # thread just finished
            th[t] = None
            return t
        else:                                   # keep searching
            t = (t+1) % len(th)
            if t == thIdx:
                # already polled each slot once this call - so wait a while
                time.sleep(0.1)

# Wait for threads to complete, marking them as None when done. Get logging results text back from queue, as this is
# thread-safe and process-safe
def gatherThreads(logger, th, gatherTimeout):
    for i, tj in enumerate(th):
        if tj:
            tj.join(timeout=gatherTimeout)  # for safety in case a thread hangs, set a timeout
            if tj.is_alive():
                logger.error('Thread {} timed out'.format())
            th[i] = None

# consume a list of files, delegating to worker threads / processes
def consumeFiles(logger, fnameList, cfg):
    try:
        shareRes, startTime, maxThreads = startConsumeFiles(logger, cfg, len(fnameList))
        countDone = 0
        signalsTrafficPrefix = cfg.get('Signals_Traffic_Prefix', '')
        if signalsTrafficPrefix:
            maxDayCount = 0
            activeDigitDays = 0
            signalsOpenDays= []
            for i in range(0, 10):
                daystr = cfg.get('Digit'+str(i)+'_Days', 0)
                dayset = {int(j) for j in daystr.split(',') }
                signalsOpenDays.append(dayset)            # list of sets
                maxDayCount = max(maxDayCount, len(dayset))
                activeDigitDays += len(dayset)
            activeDigitDensity = activeDigitDays/(10*maxDayCount)
        else:
            activeDigitDensity = 1.0
        probs = getBounceProbabilities(cfg, activeDigitDensity, logger)
        logger.info(probs)
        openClickTimeout = cfg.getint('Open_Click_Timeout', 30)
        gatherTimeout = cfg.getint('Gather_Timeout', 120)
        userAgents = getUserAgents(cfg, logger)
        doneMsgFileDest = cfg.get('Done_Msg_File_Dest')
        if probs:
            th, thSession = initThreads(maxThreads)
            resultsQ = queue.Queue()
            thIdx = 0                                       # round-robin slot
            for fname in fnameList:
                if os.path.isfile(fname):
                    # check and get a free process space
                    thIdx = findFreeThreadSlot(th, thIdx)
                    th[thIdx] = threading.Thread(target=processMail, args=(fname, probs, shareRes, resultsQ, thSession[thIdx], openClickTimeout, userAgents, signalsTrafficPrefix, signalsOpenDays, doneMsgFileDest))
                    th[thIdx].start()                      # launch concurrent process
                    countDone += 1
                    emitLogs(resultsQ)
            # check any remaining threads to gather back in
            gatherThreads(logger, th, gatherTimeout)
            emitLogs(resultsQ)
    except Exception as e:                                  # catch any exceptions, keep going
        print(e)
        logger.error(str(e))
    stopConsumeFiles(logger, shareRes, startTime, countDone)


def emitLogs(resQ):
    while not resQ.empty():
        logger.info(resQ.get())  # write results to the logfile

# -----------------------------------------------------------------------------
# Set up probabilistic model for incoming mail from config
# -----------------------------------------------------------------------------

# Set conditional probability in mutable dict P for event a given event b. https://en.wikipedia.org/wiki/Conditional_probability
def checkSetCondProb(P, a, b, logger):
    aGivenbName = a + '_Given_' + b
    PaGivenb = P[a] / P[b]
    if PaGivenb < 0 or PaGivenb > 1:
        logger.error('Config file problem: {} and {} implies {} = {}, out of range'.format(a, b, aGivenbName, PaGivenb))
        return None
    else:
        P[aGivenbName] = PaGivenb
        return True

# For safety, clip values to lie in range 0.0 <= n <= 1.0
def probClip(n):
    return max(0.0, min(1.0, n))

# Take the overall percentages and adjust them according to how much traffic we expect to receive. This app would not see
# the 'upstream handled' traffic percentage as PMTA blackholes / in-band-bounces this automatically via PMTA config, not in this application
# Express all values as probabilities 0 <= p <= 1.0
#
# For Signals, scale the open factor to allow for the filtering by active digit density
def getBounceProbabilities(cfg, activeDigitDensity, logger):
    try:
        thisAppTraffic  = 1 - cfg.getfloat('Upstream_Handled') / 100
        P = {
            'OOB'       : cfg.getfloat('OOB_percent') / 100 / thisAppTraffic,
            'FBL'       : cfg.getfloat('FBL_percent') / 100 / thisAppTraffic,
            'Open'      : cfg.getfloat('Open_percent') / 100 / thisAppTraffic,
            'OpenAgain' : cfg.getfloat('Open_Again_percent') / 100 / thisAppTraffic,
            'Click'     : cfg.getfloat('Click_percent') / 100 / thisAppTraffic,
            'ClickAgain': cfg.getfloat('Click_Again_percent') / 100 / thisAppTraffic
        }
        # Adjust open rates according to Signals periodic traffic profile, if present
        weeklyCycleOpenList = cfg.get('Weekly_Cycle_Open_Rate', '1.0').split(',')
        weeklyCycleOpenRate = [float(i) for i in weeklyCycleOpenList]
        todayOpenFactor, _ = nWeeklyCycle(weeklyCycleOpenRate, datetime.utcnow())
        todayOpenFactor = probClip(todayOpenFactor/activeDigitDensity)
        P['Open'] = probClip(P['Open'] * todayOpenFactor)
        P['OpenAgain'] = probClip(P['OpenAgain'] * todayOpenFactor)
        P['Click'] = probClip(P['Click'] * todayOpenFactor)
        P['ClickAgain'] = probClip(P['ClickAgain'] * todayOpenFactor)

        # calculate conditional open & click probabilities, given a realistic state sequence would be
        # Open?
        #  - Maybe OpenAgain?
        #  - Maybe Click?
        #     - Maybe ClickAgain?
        if checkSetCondProb(P, 'OpenAgain', 'Open', logger) \
                and checkSetCondProb(P, 'Click', 'Open', logger) \
                and checkSetCondProb(P, 'ClickAgain', 'Click', logger):
            return P
        else:
            return None
    except (ValueError, configparser.Error) as e:
        logger.error('Config file problem: '+str(e))
        return None

# Get a list of realistic User Agent strings from the specified file in config
def getUserAgents(cfg, logger):
    uaFileName = cfg.get('User_Agents_File')
    if os.path.isfile(uaFileName):
        with open(uaFileName, newline='') as uaFile:
            ua = csv.DictReader(uaFile)
            uaStringList = []
            for u in ua:
                uaStringList.append(u['Software'])
            return uaStringList
    else:
        logger.error('Unable to open User_Agents_File '+uaFileName)
        return None

# -----------------------------------------------------------------------------
# Main code
# -----------------------------------------------------------------------------

parser = argparse.ArgumentParser(description='Consume inbound mails, generating opens, clicks, OOBs and FBLs. Config file {} must be present in current directory.'.format(configFileName()))
parser.add_argument('directory', type=str, help='directory to ingest .msg files, process and delete them', )
parser.add_argument('-f', action='store_true', help='Keep looking for new files forever (like tail -f does)')
args = parser.parse_args()

cfg = readConfig(configFileName())
logger = createLogger(cfg.get('Logfile', baseProgName() + '.log'),
    cfg.getint('Logfile_backupCount', 10))

if args.directory:
    if args.f:
        # Process the inbound directory forever
        while True:
            fnameList = glob.glob(os.path.join(args.directory, '*.msg'))
            if fnameList:
                consumeFiles(logger, fnameList, cfg)
            time.sleep(5)
            cfg = readConfig(configFileName())                  # get config again, in case it's changed
    else:
        # Just process once
        fnameList = glob.glob(os.path.join(args.directory, '*.msg'))
        if fnameList:
            consumeFiles(logger, fnameList, cfg)