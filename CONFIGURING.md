# Operation

Send email traffic through SparkPost to the domains below. Mail is handled according to the subdomain

### Statistical model

## Bounces (in-band) and quiet mail acceptance

A realistic sink accepts most mail (i.e. a 250OK response) and bounces a small portion. PMTA has an in-built facility to do this.

## Opens and Clicks
If an HTML mail part is present, the sink opens ("renders") the mail by fetching any `<img .. src="..">` tags present in the received mail.

The sink clicks links by fetching any  `<a .. href="..">` tags present in the received mail.

## FBLs: MX and To address

The sink responds to a port of mails with an FBL back to SparkPost in ARF format.  The reply is constructed as follows:

- the _from_ address is the received mail _To:_ header value.
- the header '_to_' address and SMTP `RCPT TO` is as per the following table
- the sink checks the MX points to SparkPost (to avoid risk of backscatter spam)
- the ARF-format FBL mail is delivered directly over SMTP to the relevant MX (choosing the first MX if there is more than one).
PMTA pickup/queuing is not used, so that the FBL mail acceptance state is known and logged.

|Service |MX |fblTo |
|--------|---|------|
|SparkPost|smtp.sparkpostmail.com|`fbl@sparkpostmail.com`|
|SparkPost Enterprise|*tenant*.mail.e.sparkpost.com|`fbl@`_`tenant`_`.mail.e.sparkpost.com`
|SparkPost EU|smtp.eu.sparkpostmail.com|`fbl@eu.sparkpostmail.com`|

The FBLs show up as `spam_complaint` events in SparkPost.

## Bounces (out-of-band)

OOB bounces work sa follows

-- add more detail

The OOBs show up as `out_of_band` events in SparkPost.

## Delayed messages (4xx aka tempfails)

## .ini file

## Logfiles
