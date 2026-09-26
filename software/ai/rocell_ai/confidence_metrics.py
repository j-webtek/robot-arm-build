"""Descriptive offline confidence metrics; not a qualification decision."""
import math


def score(probabilities, outcomes, *, threshold=0.95, bins=10):
    if not probabilities or len(probabilities)!=len(outcomes):
        raise ValueError('nonempty equal-length scores and outcomes required')
    if type(threshold) not in (int,float) or not math.isfinite(threshold) or not 0<=threshold<=1:
        raise ValueError('invalid threshold')
    if type(bins) is not int or not 1<=bins<=100:
        raise ValueError('invalid bin count')
    if any(type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1 for p in probabilities):
        raise ValueError('invalid probability')
    if any(type(y) is not bool for y in outcomes):
        raise ValueError('outcomes must be booleans')
    n=len(outcomes);accepted=[i for i,p in enumerate(probabilities) if p>=threshold]
    false_accepts=sum(not outcomes[i] for i in accepted)
    reliability=[]
    for b in range(bins):
        indexes=[i for i,p in enumerate(probabilities) if min(int(p*bins),bins-1)==b]
        reliability.append(dict(bin_index=b,count=len(indexes),
            mean_probability=sum(probabilities[i] for i in indexes)/len(indexes) if indexes else None,
            success_fraction=sum(outcomes[i] for i in indexes)/len(indexes) if indexes else None))
    rate=sum(outcomes)/n
    return dict(count=n,brier_score=sum((p-int(y))**2 for p,y in zip(probabilities,outcomes))/n,
        outcome_frequency=rate,constant_frequency_brier=rate*(1-rate),
        accepted_count=len(accepted),abstained_count=n-len(accepted),
        acceptance_fraction=len(accepted)/n,false_accept_count=false_accepts,
        false_accept_fraction_among_accepted=false_accepts/len(accepted) if accepted else None,
        reliability_bins=reliability,
        limitation='Descriptive correlated-sample metrics; no population confidence or qualification claim')
