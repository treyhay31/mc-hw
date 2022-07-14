# Data Tracker

This application tracks a small set of [Bitcoin](https://bitcoin.org/) and [Ethereum](https://ethereum.org/en/) crypotcurrency quotes for multiple currencies:

- btceur
- btcgbp
- btcjpy
- btcusd
- btcusdc
- btcusdt
- etheur
- ethgbp
- ethjpy
- ethusd
- ethusdc
- ethusdt

*TODO: update naming and 'metrics' tracked to make more sense. 'metric' throughout the code base can probably be referred to as 'priceToCurrency' and we may want to handle other types of metrics like 'tradeCount'.*

The current application can be accessed:

https://jzf1aj3eu2.execute-api.us-east-1.amazonaws.com/metrics

```
Deploying btc-data-tracker to stage dev (us-east-1, "default" provider)

✔ Service deployed to stack btc-data-tracker-dev (63s)

us-east-1
endpoints:
  GET - https://jzf1aj3eu2.execute-api.us-east-1.amazonaws.com/metrics
  GET - https://jzf1aj3eu2.execute-api.us-east-1.amazonaws.com/metrics/{metric}
functions:
  rateHandler: btc-data-tracker-dev-rateHandler (34 MB)
  getMetrics: btc-data-tracker-dev-getMetrics (34 MB)
```

**Endpoints Explained:**

- https://jzf1aj3eu2.execute-api.us-east-1.amazonaws.com/metrics
  - Returns a list of metrics that are _tracked_ by the application
    - tracking, means that we are grabbing their latest quote every 1 minute from https://cryptowat.ch/ using the kraken market
- https://jzf1aj3eu2.execute-api.us-east-1.amazonaws.com/metrics/ethusd
  - Returns:
    - the last 24 hours of data for the provided _metric_ (timestamp & price per minute)
    - ranking of average price when compared against all of the tracked metrics
    - the average price over the last 24 hours

## Up and Running

To run your own instance of this application, you will need:

1.  [AWS Account](https://portal.aws.amazon.com/billing/signup?nc2=h_ct&src=header_signup&redirect_url=https%3A%2F%2Faws.amazon.com%2Fregistration-confirmation#/start/email)
1.  [Serverless Framework Account](https://www.serverless.com/framework)
    - this framework will require a programmatic user from your AWS account
    - TODO: setup a secret manager
1.  [Influx DB Cloud Account](https://cloud2.influxdata.com/signup)
    - The application expects two buckets to be created
      - BTC
      - BTC_24hr_rank
      - \* no need to create any schema, the app will take care of that
      - TODO: name buckets more appropriately

### Install

With [npm](https://www.npmjs.com/):

```shell
npm install -g serverless
```

Without npm:

```shell
curl -o- -L https://slss.io/install | bash
```

### Run

Create the aws resources required to run:

```shell
serverless deploy
```

Follow the CLI output to the REST API url or run the following:

```shell
serverless invoke -f getMetrics
```
  
## Frameworks & Services Used

The frameworks and services used to track this data:

- [Serverless Framework](https://www.serverless.com/framework/docs)
  - a simple app creation framework that hooks us into AWS with minimal setup/configuration
  - TODO: extract infrastructure into terraform or cloudformation in order to gain functionality not supported by the framework
- [AWS](https://aws.amazon.com/)
  - the preferred cloud provider
  - TODO: support multi cloud if required
- Python
  - 3.8
  - packages:
    - requests
    - influxdb-client
  - TODO: extract code into more modular components/classes
  - TODO: add unit tests
- [Datastore -- influxDB](https://www.influxdata.com/products/influxdb-cloud/)
  - TODO: abstract data logic in code to become more flexible when it comes to data providers 
  - TODO: learn best practices for timeseries data and implement

## Optimizations

All of the current aspects of this data tracker were chosen in order to ship quickly and inexpensively.

### Scalability

If the priorities of this data tracker were to change, here are the scenarios that we could account for:

1.  What would you change if you needed to track many metrics?
    - Depending on how many metrics we want to track, our schema may need to be optimized 
        - I am a little new to timeseries data, so I am not sure exactly what an efficient schema/structure would look like for our use-case
    - If the number of metrics increases enough, our ranking algorithm/query may need to be optimized or we may need to run a computation after every write to the database
      - This could be a trigger or in influxDB it would be a task
1.  What if you needed to sample them more frequently?
    - Using serverless functions might be the wrong approach if we increase the sample frequency.
      - At 1 request/min we execute:
        - 43,800 requests/month
        - 525,600 requests/year
      - At 1 request/30seconds we execute:
        - 87,600 requests/month
        - 1,051,200 requests/year
      - AWS Lamdba charges per request and request duration
        - depending on how many users we intend to support, the price of hosting a traditional server may end up being more cost effective
    - cryptowat.ch has a web socket API which would allow us to maintain a persistent connection and stream updates of the data
      - depending on the frequency and websocket API pricing, this might be the best approach for us to take
1.  What if you had many users accessing your dashboard to view metrics?
    - If we obtain many users, two potential bottlnecks will be:
      - 1. Incoming requests
        - By default [AWS API gateway can handle 10,000 requests/second per account/region](https://docs.aws.amazon.com/apigateway/latest/developerguide/limits.html#apigateway-account-level-limits-table)
        - By default [AWS Lambda allows 1000 concurrent function instances per region](https://docs.aws.amazon.com/lambda/latest/dg/invocation-scaling.html)
        - If either these limits are reached, we would need to distribute the functions across multiple regions and/or request quota increases from AWS
      - 2. Access to the database
        - Writing to the database will not change but reading from the database may require creating read replicas of our database that can serve a larger number of users

### Testing

Testing for our data tracker should involve:

- Unit testing of the core logic in python
  - getMetrics
    - inputs:
    - outputs: list of the metrics we track
  - getMetrics/{metric-id}
    - inputs: price
    - outputs: appropriately modeled data with rank
      - handle BAD scenarios:
        - metrics that don't exist
        - script/code as input
      - handle GOOD scenarios:
        - metrics that do exist
  - uploadData
    - inputs:
    - outputs: log statement or confirmation that data was or was NOT uploaded
      - handle BAD scenarios:
        - can't connect to DB
        - can't connect to cryptowat.ch
- Integration testing
  - make requests to API endpoints and confirm that they are returning appropriate data
    - compare outputs against what is in the database
    - compare outputs to cryptowat.ch

### Feature Proposal

> To help the user identify opportunities in real-time, the app will send an alert whenever a metric exceeds 3x the value of its average in the last 1 hour.
>
> For example, if the volume of GOLD/BTC averaged 100 in the last hour, the app would send an alert in case a new volume data point exceeds 300.

Using InfluxDB in the cloud allows us to create & manage "Check"s. A check allows us to run an aggregate function on our data and send an alert if we cross a certain data threshold. In this case we would need to keep an hourly average of our metrics. This could be updated on each write to our database or on a schedule. Our operations would look like:

1.  Get cryptowat.ch data (every 1 minute)
1.  Write data to InfluxDb
    - On write, trigger hourly_avg task
    - hourly_avg task:
      - sum each of the metrics in each of the records from the past hour
      - divide those by 60 (because we sample every minute)
      - write those values to a separate table
1.  Create check that looks at the latest record in source table and compares to the latest record in the hourly_avg task table
