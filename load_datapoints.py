import json
from smartcharts.models import DataPoint


def add_preppred_datapoints():
    with open("prepared_datapoints.jsonl") as f:
        for line in f.readlines():
            obj = json.loads(line)

            DataPoint.objects.create(
                identifier=obj["display_name"],
                display_name=obj["title"],
                lesp_code=obj["lesp_code"],
            )

