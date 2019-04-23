# How to troubleshoot and avoid rate limit issues with Splunk

## General

This Add-on is built to be aware of rate limits and is programmed to avoid exhausting them to the best of its ability.

The Add-on employs an adaptive throttling policy that will adaptively slow the API calls based on the percentage of available calls and the time remaining in the rate limit window as conveyed by the [rate limit response headers](https://developer.okta.com/docs/api/getting_started/rate-limits/#check-your-rate-limits-with-okta-s-rate-limit-headers).  By default the add-on will begin self-throttling when 80% of the available calls have been used (*20 Throttling Threshold Pct*).  You can increase the *Throttling Threshold Pct* setting causing the add-on to begin self-throttling more aggressively.

### I'm seeing rate limit warnings or violations

If you find that you are seeing multiple [violations](https://developer.okta.com/docs/api/resources/event-types?q=rateli#systemorgratelimitviolation) and not just [warnings](https://developer.okta.com/docs/api/resources/event-types?q=rateli#systemorgratelimitwarning) it is likely that you have *OTHER* clients interacting with the SAME APIs and those clients are exhausting the available API calls at a faster rate than this add-on is capable of adjusting for.  To determine the various sources look at the [actor](https://developer.okta.com/docs/api/resources/system_log#actor-object) and [client](https://developer.okta.com/docs/api/resources/system_log#client-object) objects in the warning or violation logs.
 
If possible adjust the behavior of other clients and see if that addresses the issue, it is impossible for this add-on to completely avoid causing a rate limit warning or violation if there are poorly behaving clients consuming the available rate limit.
 
### Find the afflicted endpoint and offending client

If you find that you are still experiencing warnings and violations the next step is to determine which API endpoint is being affected, you'll find this in the warning or violation log message, look in the [debugContext.debugData](https://developer.okta.com/docs/api/resources/system_log#debugcontext-object) and [target](https://developer.okta.com/docs/api/resources/system_log#target-object) objects.

Once you've determined the Okta API endpoint refer to the table below to identify the responsible Splunk input and a link to more information about the data provided by that input.

| API URI | Input | Data type reference |
|----------|-------------|----------------------------------|
| /api/v1/logs | Log | [Log Input](https://github.com/mbegan/Okta-Identity-Cloud-for-Splunk/blob/master/README/FAQ_DataTypes.md#log-apiv1logs) |
| /api/v1/users | User | [User Input](https://github.com/mbegan/Okta-Identity-Cloud-for-Splunk/blob/master/README/FAQ_DataTypes.md#user-apiv1users) |
| /api/v1/groups | Group | [Group Input](https://github.com/mbegan/Okta-Identity-Cloud-for-Splunk/blob/master/README/FAQ_DataTypes.md#group-apiv1groups) |
| /api/v1/apps/ | App | [App Input](https://github.com/mbegan/Okta-Identity-Cloud-for-Splunk/blob/master/README/FAQ_DataTypes.md#app-apiv1apps) |

Refer below for guidance on overcoming this rate limit warning.

## All endpoints

For all inputs you can increase the *Throttling Threshold Pct* causing the Add-on to be more agressivley throttle itself.

## Log [/api/v1/logs](https://developer.okta.com/docs/api/resources/system_log/#attributes)

Given the behavior, volume and default rate limits for this endpoint it is unlikely that you'll see frequent or sustained violations or warnings.  Frequent rate limit warnings or violations on this endpoint is likely an indication of a larger problem.  Infrequent warnings or violations can safely be acknowledged as minor bursts in activity, the data collection will resume in a near immediate fashion and there is no risk of lost data only a minor delay (less than 1 minute) to the collection of logs.
 
## User [/api/v1/users](https://developer.okta.com/docs/api/resources/users/#user-properties)

- Adjust the input frequency to be daily
- Set the job to run at a low user / admin volume time of the day

## Group [/api/v1/groups](https://developer.okta.com/docs/api/resources/groups/#group-attributes)

- Adjust the input frequency to be daily
- Set the job to run at a low user / admin volume time of the day

## App [/api/v1/apps](https://developer.okta.com/docs/api/resources/apps/#application-properties)

This input is a very expensive input, to get a rough estimate of how many API calls will be required to collect this data use this formula.
 
(Number of Users) * (Number of Apps) / 200
 
For a modest sized company with 1000 users and 10 apps this is only 50 API calls
For a bigger company with 10,000 users and 50 apps this is 2,500 API calls
For a large company with 100,000 users and 100 apps this is 50,000 API calls
 
Because this API doesn't support filters for lastUpdated it will require this same number of API calls every time the job runs.
 
Given what the data is it is important to keep these things in mind:

- The volatility of this data is low
- The overall value of this data is minimal in most cases
- The risk associated with this data being out of date or missing is insignificant
  - The transactional data comes from the logs metric
  
#### Suggested changes

- Adjust the input frequency to be Weekly
 Set the job to run at a low user / admin volume time of the day

## Other questions and information

### How do i set the input to run at a specific time of the day

This isn't really something you get to control but the add-on will run when the input is defined or enabled and this becomes the starting point for the schedule.  With that in mind if you had a job that was running daily you could disable it and then enable it at the time of the day you want it to run and it will, for the most part, execute at that time of the day.

### How do i know if rate limit avoidance is working?

Coming Soon

### How do i know if my log collection is keeping up?

Coming Soon

### I'm getting warnings, how do i make it stop

Alerts relative to warnings is a new issue that has come up.  The rate limit response headers do not allow for programatic enumeration of the rate limit warning threshold and it isn't a fixed value.  I am working on an to [Add new param to account for rate limit warning threshold](https://github.com/mbegan/Okta-Identity-Cloud-for-Splunk/issues/19)
