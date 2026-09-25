"""Offline analysis of retained local shoulder-pair mapping evidence."""
from __future__ import annotations

from collections import defaultdict


def analyze_mapping_rows(sources: list[dict[str, object]]) -> dict[str, object]:
    """Summarize command/endpoint plateaus without fitting a control model."""
    rows=[]
    for source in sources:
        label=source["label"]
        for row in source["rows"]:
            normalized=dict(row)
            normalized["source_label"]=label
            rows.append(normalized)
    if not rows:
        raise ValueError("Mapping rows required")

    commands=defaultdict(list);endpoints=defaultdict(list);directions=defaultdict(list)
    for row in rows:
        command=int(row["target"][0]);actual=int(row["actual"][0])
        commands[command].append(actual)
        endpoints[actual].append({"command":command,"direction":int(row["approach_direction"]),
                                  "source":row["source_label"],"leg":int(row["leg"])})
        directions[int(row["approach_direction"])].append({"command":command,"actual":actual})

    command_response={}
    for command,values in sorted(commands.items()):
        command_response[str(command)]={"samples":len(values),"endpoints":values,
            "minimum":min(values),"maximum":max(values),"span":max(values)-min(values)}
    endpoint_plateaus={str(endpoint):members for endpoint,members in sorted(endpoints.items())
                       if len(members)>1}
    direction_summary={}
    for direction,values in sorted(directions.items()):
        residuals=[row["actual"]-row["command"] for row in values]
        direction_summary[str(direction)]={"samples":len(values),
            "residual_min":min(residuals),"residual_max":max(residuals),
            "residual_mean":sum(residuals)/len(residuals)}

    return {"schema":"rocell.local_pair_mapping_analysis.v1",
        "source_labels":[source["label"] for source in sources],"rows":len(rows),
        "command_response":command_response,"endpoint_plateaus":endpoint_plateaus,
        "direction_summary":direction_summary,
        "observed_primary_range":[min(endpoints),max(endpoints)],
        "interpretation":{
            "repeatable_upper_anchor":command_response.get("2389"),
            "repeatable_lower_anchor":command_response.get("2377"),
            "history_dependent_plateaus_observed":bool(endpoint_plateaus),
            "random_delivery_failure_supported":False,
        },
        "model_fitted":False,"compensation_promoted":False,
        "general_compensation_validated":False,"cartesian_accuracy_validated":False,
        "movement_authorized":False,"hardware_access_during_analysis":False}
