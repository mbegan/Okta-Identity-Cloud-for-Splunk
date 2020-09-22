# Okta Identity Cloud Add-on

The primary purpose of this Add-On is to collect time series event data from Okta using the Okta [System Log](https://developer.okta.com/docs/reference/api/system-log/) API.  This Add-On also contains the ability to ingest Okta Universal Directory (UD) using Okta's [Users](https://developer.okta.com/docs/reference/api/users/), [Groups](https://developer.okta.com/docs/reference/api/groups/) and [Apps](https://developer.okta.com/docs/reference/api/apps/) APIs.

This guide will cover the steps required to ingest Log data from Okta.  

The steps required to ingets UD data are similar but not covered here and I suggest that you NOT configure them unless you have a specific use case for ingesting directory state data.

# Getting Started

## Prerequisites

This add-on will require the Okta Domain and the API Token for an Administrative Account in that Okta Domain.  We recommend creating a dedicated service account for this purpose and assigning the minimum privleges.  Use the [Create and API Token](https://developer.okta.com/docs/guides/create-an-api-token/overview/) guide for detailed steps.

## Install

We can now install the Add-on in our Splunk environment.  This add-on is primarily a tool for collecting logs and is only required to be installed a heavy forwarder.  It does contain saved searches and other knowledge objects so installation on search heads is helpful.  Only configure an input on one Splunk server.

- Install via the Splunk webapp (recommended) or manually copy and expand the app into $SPLUNK_HOME/etc/apps/ location
- Restart the Splunk server

## Configure Settings (optional)

Using the Splunk webapp, login and launch the newly installed Okta Identity Cloud Add-on.

The default settings are appropriate in most cases.  Be aware of the advanced `Add-on Settings` and `Logging` available in the `Configuration` menu.

### Rate limits and adaptive self-throttling

* Navigate to Configuration -> Add-on Settings

There are 3 settings related to rate limits and the adaptive throttling / rate limit avoidance strategy the add-on uses.

__Avoid Rate Limit Warnings__: _Enable throttling logic that attempts to avoid exceeding API throttling warning limits_

__Warning Threshold Percentage__: _Used to adjust rate limit avoidance target. Tells add-on to use ONLY this percentage of API calls. Defaults to 50%_

__Throttling Threshold Pct__: _below this percentage of available rate limits an adaptive throttling strategy is leveraged_

The strategy is as follows:

Keep in mind that rate limits are shared among clients and we cannot assune we are the only client.

After each API call is made the [response headers](https://developer.okta.com/docs/reference/rl-best-practices/#check-your-rate-limits-with-okta-s-rate-limit-headers) are evaluated to determine what the rate limit is, the number of remaining calls and the ammount of time left in the rate limit window.

If the response code was a 429 we exceeded the client will pause for the time left in the rate limit window + 7 seconds for a safety factor (67 seconds would be the max)

  - If the response a 200 code (success) the client will evaluate the time left in the rate limit window along with the number of remaining calls available
    - If __Avoid Rate Limit Warnings__ is enabled (please leave this enabled) the number of remaining calls evaluated from the response headers is reduced to the __Warning Threshold Percentage__ of the actual remaining calls.
    - _e.g. if the reponse header says there are 100 calls available and the __Warning Threshold Percentage__ is set to 75% the remaining logic will act as if there are only 75 remaining calls_
  - To decide how long the client should pause it makes an assumption about the number of calls per second it and other clients are making (4 calls per second)
    - If the calculated number of expected calls exceeds the calculated remaining calls the client will pause more agressivley
  - Finally the client will pause for the calcualted pause time IF percentage of calculated available calls exceeds the defined __Throttling Threshold Pct__

## Define Account

Using the Splunk webapp, login and launch the newly installed Okta Identity Cloud Add-on.

Before we can define an input we must provide account credentials.  Using the `Okta Domain` and `API Token` from our [Prerequisites](#Prerequisites) section perform the following.

* Navigate to Configuration -> Okta Accounts
* Click `Add`
* Provide a unique and appropriate `Okta Account Name` for the account (arbitrary value)
* Enter the `Okta Domain`
* Enter the `Okta API Token`
* Click `Add`

## Define Input

With our Account defined we can now define and Input

* Navigate to Inputs
* Click `Create New Input`
* Provide a unique and appropriate `Name` for the input (arbitrary value)
* Provide the desired interval (60 seconds is recommended)
* Choose the appropriate `Index`
* Select `Logs` from the Metric dropdown (Only use Users, Groups and Apps if you have a specific use case for type of data those metrics ingest)
* Select the appropriate `Okta Account` defined in the previous step
* Click `Add`

## Search for data

All data collected by this add-on will contain a `source` of `Okta:im2` and the `host` value will be the domain of your Okta tenant _(e.g. yourdomain.okta.com)_

The `sourcetype` of the data will vary by the "metric" associated with the input.  Refer to this table for the sourcetype generated by specific metrics used in the input and a link / description of the type of data.

| Input Metric | sourcetype | API reference / Description |
|----------|-------------|----------------------------------|
| Log | `OktaIM2:log` | [Log Object](https://developer.okta.com/docs/api/resources/system_log/#attributes) |
| User | `OktaIM2:user` | [User Object](https://developer.okta.com/docs/api/resources/users/#user-properties) |
| Group | `OktaIM2:group` | [Group Object](https://developer.okta.com/docs/api/resources/groups/#group-attributes) |
| Group | `OktaIM2:groupUser` | made up object to help Splunk, just a simple user to group mapping object |
| App | `OktaIM2:app` | [App Object](https://developer.okta.com/docs/api/resources/apps/#application-properties) |
| App | `OktaIM2:appUser` | made up object to help Splunk, a truncated version of an [appUser Object](https://developer.okta.com/docs/api/resources/apps/#application-user-properties) useful for maping a user to an app along with some high level metadata about the assginement |

Refer to the descriptions below for each type of data for additional context relative to Splunk.

### Log [/api/v1/logs](https://developer.okta.com/docs/api/resources/system_log/#attributes)
 
This input is responsible for the ingesting all of the transactional events occurring in your Okta org it is the *most important* input provided by this add-on and should be configured to retrieve its data in a near real time manner.

Refer to the API documentation for a detailed explaination of the data model.  You can also review the [event type catalog](https://developer.okta.com/docs/api/resources/event-types) additional insight into the meaning of specific event types you will see.

#### Sample Log

```
{
    "actor": {
		"id": "00u8tvgeu9PoK3xRB0h7",
		"type": "User",
		"alternateId": "mbegan@okta.com",
		"displayName": "Matthew Egan",
		"detailEntry": null
	},
	"client": {
		"userAgent": {
			"rawUserAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.89 Safari/537.36",
			"os": "Mac OS X",
			"browser": "CHROME"
		},
		"zone": "null",
		"device": "Computer",
		"id": null,
		"ipAddress": "73.63.112.167",
		"geographicalContext": {
			"city": "Ogden",
			"state": "Utah",
			"country": "United States",
			"postalCode": "84401",
			"geolocation": {
				"lat": 41.2214,
				"lon": -111.9624
			}
		}
	},
	"authenticationContext": {
		"authenticationProvider": null,
		"credentialProvider": null,
		"credentialType": null,
		"issuer": null,
		"interface": null,
		"authenticationStep": 0,
		"externalSessionId": "102qxa2cQbJQViQis88bc-luw"
	},
	"displayMessage": "User accessing Okta admin app",
	"eventType": "user.session.access_admin_app",
	"outcome": {
		"result": "SUCCESS",
		"reason": null
	},
	"published": "2020-07-28T14:05:01.090Z",
	"securityContext": {
		"asNumber": 7922,
		"asOrg": "comcast",
		"isp": "comcast cable communications llc",
		"domain": "comcast.net",
		"isProxy": false
	},
	"severity": "INFO",
	"debugContext": {
		"debugData": {
			"requestId": "XyAwjOeTMrGczq2OgVx0egAAABQ",
			"requestUri": "/admin/sso/request",
			"threatSuspected": "false",
			"url": "/admin/sso/request?"
		}
	},
	"legacyEventType": "app.admin.sso.login.success",
	"transaction": {
		"type": "WEB",
		"id": "XyAwjOeTMrGczq2OgVx0egAAABQ",
		"detail": {}
	},
	"uuid": "53d1e0b0-d0db-11ea-9210-815689eddc18",
	"version": "0",
	"request": {
		"ipChain": [{
			"ip": "73.63.112.167",
			"geographicalContext": {
				"city": "Ogden",
				"state": "Utah",
				"country": "United States",
				"postalCode": "84401",
				"geolocation": {
					"lat": 41.2214,
					"lon": -111.9624
				}
			},
			"version": "V4",
			"source": null
		}]
	},
	"target": [{
		"id": "00u8tvgeu9PoK3xRB0h7",
		"type": "AppUser",
		"alternateId": "mbegan@okta.com",
		"displayName": "Matthew Egan",
		"detailEntry": null
	}]
}
```

### User [/api/v1/users](https://developer.okta.com/docs/api/resources/users/#user-properties)
 
User objects are JSON representations of user objects in Okta Universal Directory.  This isn't a transactional stream of "events" relative to users, rather a sync or replica of users from Okta.  This data type can be be used to enrich log data retrieved from the log input, it could also be useful for performing adhoc and complex queries and analysis of your user population.
 
When this input is initially configured it will need to sync ALL of the user objects from Okta into Splunk.  On subsequent job intervals the input will only retrieve user objects that have been modified since the last collection (deltas).

#### Sample User

```
{
    "id": "00urcn839yCU45hoG0h7",
	"status": "ACTIVE",
	"created": "2020-05-04T20:44:45.000Z",
	"activated": "2020-05-04T20:44:47.000Z",
	"statusChanged": "2020-05-04T20:44:47.000Z",
	"lastLogin": null,
	"lastUpdated": "2020-05-04T20:44:47.000Z",
	"passwordChanged": "2020-05-04T20:44:47.000Z",
	"type": {
		"id": "oty8tvgeqxbtt6mKk0h7"
	},
	"profile": {
		"firstName": "Matthew",
		"lastName": "Adams",
		"mobilePhone": null,
		"secondEmail": "",
		"login": "madam@regionalinsurance.zz",
		"email": "madam@regionalinsurance.zz"
	},
	"credentials": {
		"password": {},
		"provider": {
			"type": "OKTA",
			"name": "OKTA"
		}
	}
}
```

### Group [/api/v1/groups](https://developer.okta.com/docs/api/resources/groups/#group-attributes)

Group objects are JSON representations of groups object in Okta Universal Directory, it is also used to enumerate group memberships**.  This isn't a transactional stream of "events" relative to groups, rather a sync or replica of groups from Okta or other connected directories and applications.  This data type  can be used to enrich log data retrieved from the log input, it could also be useful for performing adhoc and complex queries and analysis of your groups and group memberships.
 
When this input is initially configured it will need to sync ALL of the group objects from Okta into Splunk.  On subsequent job intervals the input will only retrieve group objects that have been modified since the last collection (deltas).

#### Sample Group

```
{
    "id": "00grcnm2l6XF8pUtD0h7",
	"created": "2020-05-04T20:58:23.000Z",
	"lastUpdated": "2020-05-04T20:58:23.000Z",
	"lastMembershipUpdated": "2020-05-04T20:58:49.000Z",
	"objectClass": ["okta:user_group"],
	"type": "OKTA_GROUP",
	"profile": {
		"name": "VAP Exception",
		"description": "Users to be excluded from regular VAP Group policies"
	},
	"_embedded": {
		"stats": {
			"usersCount": 3,
			"appsCount": 0,
			"groupPushMappingsCount": 0,
			"hasAdminPrivilege": false
		}
	},
	"members": ["see groupUser sourcetype"],
	"assignedApps": []
}
```

### App [/api/v1/apps](https://developer.okta.com/docs/api/resources/apps/#application-properties)
 
App objects are JSON representations of apps objects in Okta Universal Directory, it is also used to enumerate users assigned to apps and groups related to apps -- assignment groups, groups sourced from the app or groups pushed to the app.  This isn't a transactional stream of "events" relative to apps, rather a sync or replica of apps as they are configured in Okta.  This data type can be used to enrich data retrieved from the log input, it could also be useful for performing adhoc and complex queries and analysis of your apps, their configuration as well as applications assignments.
 
#### Sample App

```
{
    "id": "0oamrm1jn2iFAYEBy0h7",
	"name": "scaleft",
	"label": "Okta Advanced Server Access",
	"status": "ACTIVE",
	"lastUpdated": "2020-07-27T05:23:06.000Z",
	"created": "2019-08-06T20:46:27.000Z",
	"accessibility": {
		"selfService": false,
		"errorRedirectUrl": null,
		"loginRedirectUrl": null
	},
	"visibility": {
		"autoSubmitToolbar": false,
		"hide": {
			"iOS": false,
			"web": false
		},
		"appLinks": {
			"scaleft_link": true
		}
	},
	"features": ["PUSH_NEW_USERS", "PUSH_USER_DEACTIVATION", "SCIM_PROVISIONING", "GROUP_PUSH", "REACTIVATE_USERS", "PUSH_PROFILE_UPDATES"],
	"signOnMode": "SAML_2_0",
	"credentials": {
		"userNameTemplate": {
			"template": "${source.login}",
			"type": "BUILT_IN"
		},
		"signing": {
			"kid": "SW2tTiRWLH0oVmf5Moi7AKf_H2Dl5lrVgufuP5LFkG8"
		}
	},
	"settings": {
		"app": {
			"audRestriction": "https://app.scaleft.com/v1/teams/oktabd-dev",
			"baseUrl": "https://app.scaleft.com"
		},
		"notifications": {
			"vpn": {
				"network": {
					"connection": "DISABLED"
				},
				"message": null,
				"helpUrl": null
			}
		},
		"signOn": {
			"defaultRelayState": null,
			"ssoAcsUrlOverride": null,
			"audienceOverride": null,
			"recipientOverride": null,
			"destinationOverride": null,
			"attributeStatements": []
		}
	},
	"assigned_users": ["see appUser sourcetype"],
	"assigned_groups": ["00gbp0p37mI2AvvEP0h7"]
}
```

### appUser

An appUser object is a truncated version of an okta [Application User Object](https://developer.okta.com/docs/reference/api/apps/#application-user-object)

Useful for understanding basic details about a users assignment to a given application.

#### Use the log data

See our [Event Types](https://developer.okta.com/docs/reference/api/event-types/?q=application.user_membership) Catalog to see transactional events.

`source="okta:im2"  sourcetype="OktaIM2:log" eventType=application.user_membership.*`


#### Sample appUser

```
{
    "appid": "0oasyjsx014fxPKg10h7",
	"userid": "00u8tvgeu9PoK3xRB0h7",
	"externalId": null,
	"userName": "mbega.n@gmail.com",
	"created": "2020-07-24T18:50:45.000Z",
	"lastUpdated": "2020-07-24T18:50:45.000Z",
	"statusChanged": "2020-07-24T18:50:45.000Z",
	"scope": "",
	"status": "ACTIVE"
}
```

### groupUser

A groupUser object is a made up object that expresses a users group membership (or a groups user membership).

Useful for building an understanding of group memberships.

#### Use the log data

See our [Event Types](https://developer.okta.com/docs/reference/api/event-types/?q=group.user_membership) Catalog to see transactional events.

`source="okta:im2"  sourcetype="OktaIM2:log" eventType=group.user_membership.*`

#### Sample groupUser

```
{
    "groupid": "00gn76moxaDjJnDdD0h7",
	"userid": "00urcn839yCU45hoG0h7"
}
```


# Troubleshooting and FAQ

## Troubleshooting

Look at the logs (`index="_internal"  sourcetype="OktaIM2:addon"` or the tail -f ta_okta_identity_cloud_for_splunk_okta_identity_cloud.log file

## FAQ

Will update as they come in


Enjoy!
