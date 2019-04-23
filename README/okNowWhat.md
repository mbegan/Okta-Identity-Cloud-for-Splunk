# I'm collecting data... now what do i do?

So you are collecting data with this add-on and now you want to know what to do... welcome to the club.  I'm going to share a few ideas here and encourage those reading and interested to ask questions or provide in put by way of issues and pull reuests.

first and foremost review the [data types](https://github.com/mbegan/Okta-Identity-Cloud-for-Splunk/blob/master/README/FAQ_DataTypes.md) doc to get a quick idea of what data is available.

That take now of the Okta [event type catalog](https://developer.okta.com/docs/api/resources/event-types).

Review the [System Log API Doc](https://developer.okta.com/docs/api/resources/system_log/#attributes) making a special note about [Event Correlation](https://developer.okta.com/docs/api/resources/system_log/#event-correlation).

After that take a look at some of the ideas the rest of this doc has to share.

## Basic queries

Get started with some basics

#### List the different sourcetypes that are present in Splunk
```sql
* source=okta:im2 | stats count by sourcetype
```
 
#### Find list apps defined in Okta by their signOnMode (good example of ways to audit how apps are setup)
```sql
* sourcetype=OktaIM2:app | stats count by signOnMode
```
 
#### Find users in Okta that aren’t Okta “mastered” and the provide a count by the provider.name (AD domain)
```sql
* sourcetype=OktaIM2:user "credentials.provider.type"!=OKTA | stats count by host, credentials.provider.name
```

#### Find your most common (or least common) eventTypes
```sql
* sourcetype=OktaIM2:log | stats count by host, eventType
```

## Specific eventTypes

Dig a little deeper with some eventType specific guides

| eventType | reference doc |
|----------|----------
| [user.session.start](https://developer.okta.com/docs/api/resources/event-types/?q=user.session.start) | [User login to Okta](https://github.com/mbegan/Okta-Identity-Cloud-for-Splunk/blob/master/README/user.session.start.md) |

Other eventTypes of note are maintained in the [Okta Event Types of Interest for Security Teams](https://github.com/OktaSecurityLabs/CheatSheets/blob/master/SecurityEvents.md)

## Patterns

Interesting patterns to detect, some of this is discussed in the eventType specific guides.  Here are some generic patterns to be on the look out for.
