import torch

def geometry_loss(coordinates,points,visible):
    """Supervised pair-vector consistency, weighted by both corners' visibility."""
    i,j=torch.triu_indices(4,4,offset=1,device=coordinates.device)
    error=((coordinates[:,i]-coordinates[:,j])-(points[:,i]-points[:,j]))/16
    weights=visible[:,i]*visible[:,j]
    return (error.square().sum(-1)*weights).sum()/weights.sum().clamp_min(1)
