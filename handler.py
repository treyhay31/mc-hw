import datetime
import logging
import json
import os
import requests
from datetime import datetime
import os

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

market = 'market:kraken'
tracked_metrics = [
    'btceur',
    'btcgbp',
    'btcjpy',
    'btcusd',
    'btcusdc',
    'btcusdt',
    'etheur',
    'ethgbp',
    'ethjpy',
    'ethusd',
    'ethusdc',
    'ethusdt'
]
org = "treyhay@gmail.com"
bucket = "BTC"


def getMetrics(event, context):

    logger.info(type(event))
    logger.info(event)

    try:
        metric = event['pathParameters']['metric']
        if metric in tracked_metrics:
            logger.info(f'we track it! -- {metric}')

            with InfluxDBClient(url="https://us-east-1-1.aws.cloud2.influxdata.com", token=os.getenv("INFLUX_TOKEN"), org=org) as client:
                query_api = client.query_api()
                query = f'from(bucket:"{bucket}")\
                |> range(start: -24h)\
                |> filter(fn: (r) => r["_measurement"] == "price")\
                |> filter(fn:(r) => r._field == "{metric}" )'
                result = query_api.query(org=org, query=query)

                results = []
                for table in result:
                    for record in table.records:
                        results.append((record.get_time(), record.get_value()))

                query = f'from(bucket:"BTC_24hr_rank")\
                |> range(start: -1h)\
                |> filter(fn: (r) => r["_measurement"] == "price")\
                |> last()'
                result = query_api.query(org=org, query=query)

                vals = []
                for table in result:
                    for record in table.records:
                        vals.append({ 
                            "coin": record.get_field(), 
                            "avg": record.get_value()
                        })

                vals.sort(key=lambda x: x['avg'], reverse=True)

                rank = 1
                averageOverLast24 = 0
                for v in vals:
                    if v['coin'] == metric:
                        break
                    rank += 1
                    averageOverLast24 = v['avg']

                client.close()

            goodResponse = {
                "statusCode": 200, 
                "body": json.dumps(
                    {
                        "message": f'querying database for {metric} and giving rank...', 
                        "data": {
                            "name": metric, 
                            "rank": rank, 
                            "averageOverLast24hr": averageOverLast24, 
                            "pricesPerMinute": results
                        }
                    }, 
                    indent=1, 
                    default=str
                )
            }
            return goodResponse
        else:
            logger.info('we dont track it...')
            badResponse = {
                "statusCode": 400, 
                "body": json.dumps(
                    {
                        "message": 'not a tracked metric', 
                        "data": {}
                    }
                )
            }
            return badResponse

    except KeyError:
        logger.info('no pathParameters, returning list of metrics')

    body = {
        "message": "Select a metric and add it to the current url `/btceur`",
        "data": tracked_metrics
    }

    response = {"statusCode": 200, "body": json.dumps(body)}

    return response


def run(event, context):

    url = "https://api.cryptowat.ch/markets/prices"

    resp = requests.get(
        url, headers={'X-CW-API-Key': os.getenv("CRYPTO_TOKEN")})
    data = resp.json()
    res = data['result']

    tracked_metric_prices = []
    for metric in tracked_metrics:
        price = res[f'{market}:{metric}']
        logger.debug(f'{metric.upper()} Price: {price}')
        tracked_metric_prices.append(price)

    with InfluxDBClient(url="https://us-east-1-1.aws.cloud2.influxdata.com", token=os.getenv("INFLUX_TOKEN"), org=org) as client:
        write_time = datetime.utcnow()
        point = Point("price") \
            .tag("host", "aws-data-tracker") \
            .time(write_time, WritePrecision.NS)

        for i in range(len(tracked_metrics)):
            point.field(tracked_metrics[i], tracked_metric_prices[i])

        write_api = client.write_api(write_options=SYNCHRONOUS)

        write_api.write(bucket, org, point)

        logger.info(f'wrote @ {write_time}')

        client.close()
