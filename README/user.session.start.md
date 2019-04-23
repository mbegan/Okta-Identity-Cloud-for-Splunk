# [user.session.start - User login to Okta](https://developer.okta.com/docs/api/resources/event-types/?q=user.session.start)

This is guidance I’ve shared with a handful of people interested in breaking down data from Okta's system log for security purposes.  I'm using a specific eventType but it can be used as general guidance when considering analysis of interesting events or event sequences.

start by running this query for a period of time in your Splunk instance.

```sql
eventType="user.session.start"
| stats count by outcome.result, debugContext.debugData.requestUri, actor.id, actor.alternateId
```

This will produce a table with the following details

|outcome.result|debugContext.debugData.requestUri|actor.id|actor.alternateId|count|
|------|------|------|------|------|
|Result of the action: SUCCESS, FAILURE, SKIPPED, UNKNOWN|details relative to the auth method used|Okta id of user logging in (unknown means invalid username used)|username (login) of user logging in|number of occurances found|

With this as a starting point you might see how Tracking and reporting on this event would help you uncover a number of things see table below for ideas and sample queries.

Notes:
- Determine the frequency and threshold that works for your org
- More than x number of failed attempts per user over _n_ minutes
- Might be worth running multiple intervals and thresholds:
  - 5 failures in 5 minutes is likely to be a user that forgot their password
  - 30 failures over 24 hours is probably not user error but detecting abuse after 24 hours might not be fast enough to prevent a breech

|Purpose|Reason|Notes|Sample Query|
|------|------|------|------------------|
|Failed attempts by User|Identify failed attempt patterns by username| . |`eventType=user.session.start outcome.result=FAILURE`\|`stats count by actor.alternateId`|
|Failed attempts by IP Address|Identify failed attempt patterns by IP address.|- Filtering out known company IP addresses|`eventType=user.session.start outcome.result=FAILURE`\|`stats count by client.userAgent.rawUserAgent`|
