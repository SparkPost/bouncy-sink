# Bouncy Sink for SparkPost traffic

Send email through SparkPost to the following domains.  Please note this counts as usage on your
account.

## Recipient Domains

Different response behaviours are available, through choice of recipient subdomain.  The localpart of the address can be anything.

|Response Behaviour|Use Recipient Address|
|-------------|--------------------------|
|Accept quietly, without opens or clicks|`any@accept.bouncy-sink.trymsys.net`|
|Out-of-band bounce|`any@oob.bouncy-sink.trymsys.net`|
|Spam Complaint (ARF format FBL) |`any@fbl.bouncy-sink.trymsys.net`|
|Accepted and opened at least once|`any@openclick.bouncy-sink.trymsys.net`|
|Statistical mix of responses|`any@bouncy-sink.trymsys.net`|

The subdomain part immediately after the `@` is checked, so `@fbl.bouncy-sink.trymsys.net` and `@fbl.fred.wilma.bouncy-sink.trymsys.net`
trigger the same behaviour.

Other subdomains, for example `foo.bar.bouncy-sink.trymsys.net` will give the statistical
mix of responses.

Open and click tracking requires a valid html part in your mail content, and the relevant tracking options
to be enabled in your SparkPost account & transmission. "Click" tries to follow all links present in the html part.

### Traffic generator

Any method can be used to generate traffic. Here is [a traffic generator](https://github.com/tuck1s/sparkpost-traffic-gen)
which can easily be deployed to Heroku, to generate random traffic through your SparkPost account towards the "bouncy sink".
Note that all sent messages count towards your account usage.

### Statistical model
This is the default setup:

<img src="bouncy-sink-statistical-model.svg"/>

This can be customised using the .ini file if you are deploying your own bouncy sink instance.


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

OOB bounces work as follows

-- add more detail

The OOBs show up as `out_of_band` events in SparkPost.

## Delayed messages (4xx aka tempfails)

