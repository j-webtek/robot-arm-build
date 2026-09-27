"""Fixed LeakyReLU research variant; v0 ReLU artifacts remain unchanged."""
from torch import nn
from vision.mask_conditioned_pose import MaskConditionedPoseNet


class LeakyMaskConditionedPoseNet(MaskConditionedPoseNet):
    def __init__(self, mode):
        super().__init__(mode)
        self.residual[1] = nn.LeakyReLU(negative_slope=0.01)

    def export(self):
        artifact = super().export()
        artifact['schema'] = 'rocell.research.mask_conditioned_pose.leaky.v1'
        artifact['negative_slope'] = 0.01
        return artifact

    @classmethod
    def from_export(cls, artifact):
        if (set(artifact) != {'schema', 'mode', 'state', 'negative_slope'} or
                artifact['schema'] != 'rocell.research.mask_conditioned_pose.leaky.v1' or
                type(artifact['negative_slope']) is not float or artifact['negative_slope'] != 0.01):
            raise ValueError('invalid fixed LeakyReLU research artifact')
        model = cls(artifact['mode'])
        model.load_state_dict(artifact['state'], strict=True)
        return model.eval()
