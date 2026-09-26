"""Precision v2: explicit abstention or externally qualified error bounds.

Qualification records are trusted application configuration, never model output.
This revision supports synthetic keyboard research only; no deployment claims.
"""
from __future__ import annotations
import math
from .scene_observation import canonical_hash, SHA256_PATTERN
from .visual_observation import validate as validate_prediction, MODEL_SCHEMA

SCHEMA = 'rocell.ai_precision_observation.v2'
FIELDS = {'schema','prediction','domain_id','qualification_sha256','abstain','abstain_reasons','observation_sha256'}
QUALIFICATION_FIELDS = {'schema','model_sha256','target_catalog_sha256','domain_id','calibration_dataset_sha256',
    'evaluation_dataset_sha256','coverage_probability','error_bound_mm','target_ids','scope','qualification_sha256'}


def validate_qualification(value):
    if not isinstance(value,dict) or set(value)!=QUALIFICATION_FIELDS or value['schema']!='rocell.ai_localization_qualification.v0':
        raise ValueError('Invalid localization qualification fields')
    if value['scope']!='SYNTHETIC_OFFLINE_ONLY':
        raise ValueError('Only synthetic offline qualification is supported')
    for key in ('model_sha256','target_catalog_sha256','calibration_dataset_sha256','evaluation_dataset_sha256','qualification_sha256'):
        if not isinstance(value[key],str) or SHA256_PATTERN.fullmatch(value[key]) is None:
            raise ValueError('Invalid qualification digest')
    if value['calibration_dataset_sha256']==value['evaluation_dataset_sha256']:
        raise ValueError('Calibration and evaluation datasets must differ')
    for key in ('coverage_probability','error_bound_mm'):
        if type(value[key]) not in (int,float) or not math.isfinite(value[key]):
            raise ValueError('Qualification bounds must be finite numbers')
    if not 0.95<=value['coverage_probability']<1 or not 0<value['error_bound_mm']<=100:
        raise ValueError('Invalid qualification coverage or error bound')
    if not isinstance(value['domain_id'],str) or not value['domain_id'].strip():
        raise ValueError('Qualification domain is required')
    ids=value['target_ids']
    if not isinstance(ids,list) or not 1<=len(ids)<=256 or any(not isinstance(k,str) or not k for k in ids) or len(set(ids))!=len(ids):
        raise ValueError('Qualification target ids must be unique')
    if value['qualification_sha256']!=canonical_hash({k:v for k,v in value.items() if k!='qualification_sha256'}):
        raise ValueError('Qualification hash mismatch')
    return value


def build(prediction, *, domain_id, qualification_sha256=None):
    core={'schema':SCHEMA,'prediction':prediction,'domain_id':domain_id,
          'qualification_sha256':qualification_sha256,'abstain':qualification_sha256 is None,
          'abstain_reasons':['localization_uncalibrated'] if qualification_sha256 is None else []}
    result={**core,'observation_sha256':canonical_hash(core)}
    validate(result)
    return result


def validate(value):
    if not isinstance(value,dict) or set(value)!=FIELDS or value['schema']!=SCHEMA:
        raise ValueError('Invalid precision v2 fields')
    prediction=value['prediction']
    if not isinstance(prediction,dict) or prediction.get('schema')!=MODEL_SCHEMA:
        raise ValueError('Precision v2 requires a keyboard image prediction')
    validate_prediction(prediction,device='keyboard',catalog_sha256=prediction.get('target_catalog_sha256'))
    if not isinstance(value['domain_id'],str) or not value['domain_id'].strip():
        raise ValueError('Precision domain is required')
    q=value['qualification_sha256']
    if q is not None and (not isinstance(q,str) or SHA256_PATTERN.fullmatch(q) is None):
        raise ValueError('Invalid localization qualification digest')
    if value['abstain'] is not (q is None) or value['abstain_reasons']!=(['localization_uncalibrated'] if q is None else []):
        raise ValueError('Precision abstention is inconsistent')
    if value['observation_sha256']!=canonical_hash({k:v for k,v in value.items() if k!='observation_sha256'}):
        raise ValueError('Precision observation hash mismatch')
    return value


def qualification_for(value, trusted_qualifications):
    validate(value)
    if value['abstain']:
        return None
    digest=value['qualification_sha256']
    if digest not in trusted_qualifications:
        return None
    q=validate_qualification(trusted_qualifications[digest])
    prediction=value['prediction']
    if q['qualification_sha256']!=digest or q['model_sha256']!=prediction['model_sha256'] or q['target_catalog_sha256']!=prediction['target_catalog_sha256'] or q['domain_id']!=value['domain_id']:
        raise ValueError('Localization qualification identity mismatch')
    return q
