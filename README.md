
# Initial setup
## AWS configuration
- EC2 Linux
- Two IP addresses

## PMTA configuration
- separate blackhole and clicky-sink operation
- delivers mails to directory
- tool runs in batch mode

# Operation

## Opens and Clicks
The sink "opens" aka "renders" the mail by fetching any `<img .. src="..">` tags present in the received mail.

The sink "clicks" links by fetching any  `<a .. href="..">` tags present in the received mail.

## FBLs: MX and To address

The sink delivers FBL mails back to SparkPost in ARF format.  The reply is constructed as follows:

- the _from_ address is the received mail _To:_ header value.
- the header '_to_' address and SMTP `RCPT TO` is as per the following table
- the message is injected via SMTP direct to the relevant MX (just choosing the first one on the list, not looking at priorities).

|Service |MX |fblTo |
|--------|---|------|
|SparkPost|smtp.sparkpostmail.com|`fbl@sparkpostmail.com`|
|SparkPost Enterprise|*tenant*.mail.e.sparkpost.com|`fbl@`_`tenant`_`.mail.e.sparkpost.com`
|SparkPost EU|smtp.eu.sparkpostmail.com|`fbl@eu.sparkpostmail.com`|

The FBLs show up as `spam_complaint` events in SparkPost.

## OOBs

## Delayed messages (4xx aka tempfails)
