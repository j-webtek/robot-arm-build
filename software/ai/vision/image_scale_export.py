"""Strict offline research scale artifact; no motion authority."""
import re
import numpy as np
from vision.image_quality_scale import features,predict_scale
SCHEMA='rocell.research.image_scale.v1'
PREPROCESS='raw_rgb_resize128x96_quality56_v1'


def validate(artifact):
    if set(artifact)!={'schema','preprocess','pose_sha256','source_sha256','feature_source_sha256','fit'} or artifact['schema']!=SCHEMA or artifact['preprocess']!=PREPROCESS:raise ValueError('invalid artifact')
    for key in ['pose_sha256','source_sha256','feature_source_sha256']:
        if not isinstance(artifact[key],str) or re.fullmatch('[0-9a-f]{64}',artifact[key]) is None:raise ValueError('invalid digest')
    fit=artifact['fit']
    if set(fit)!={'mean','scale','weights','intercept','alpha'}:raise ValueError('invalid fit')
    for key in ['mean','scale','weights']:
        x=np.asarray(fit[key],dtype=float)
        if x.shape!=(56,) or not np.isfinite(x).all():raise ValueError('invalid '+key)
    if min(fit['scale'])<=0 or not np.isfinite(fit['intercept']) or fit['alpha']!=1.:raise ValueError('invalid fit values')
    return artifact


def predict_image(artifact,image):
    validate(artifact)
    return float(predict_scale(artifact['fit'],features(image)[None])[0])
