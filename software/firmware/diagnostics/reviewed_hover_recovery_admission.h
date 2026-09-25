// Fixed, boot- and installed-release-bound r91 recovery admission framing.
// No route or motion authority is supplied by constructing this object.
#pragma once
#include "reviewed_hover_live_admission.h"
#include "reviewed_hover_recovery_policy.h"
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace rocell_diag {
struct ReviewedHoverRecoveryAdmission {
  static constexpr size_t wire_size=184;
  uint8_t recipe_digest[32]{};
  static constexpr char canonical[] =
    "{\"acceleration\":1,\"export_before_next\":true,"
    "\"hardware_access\":false,\"maximum_writes\":5,"
    "\"motion_authorized\":false,\"one_use_per_boot\":true,"
    "\"pose_ids\":[\"A_CLEAR\",\"A_HOVER\",\"A_DOWN\","
    "\"A_HOVER\",\"A_CLEAR\"],"
    "\"schema\":\"rocell.reviewed_hover_recovery_manifest.v1\","
    "\"source_pose\":\"A_HOVER\",\"speed\":20}";

  template<class Crypto>
  static bool parse(const char* body,size_t size,const uint8_t (&boot)[16],
                    const uint8_t (&release)[32],Crypto& crypto,
                    ReviewedHoverRecoveryAdmission& output){
    if(!body||size!=wire_size||std::memcmp(body,"RCHR1:",6)||
       body[38]!=':'||body[103]!=':'||body[168]!=':'||
       std::memcmp(body+169,"LIVE_NONCONTACT",15))return false;
    uint8_t supplied_boot[16]{},supplied_recipe[32]{},supplied_release[32]{};
    if(!ReviewedHoverLiveAdmission::hex(body+6,16,supplied_boot)||
       !ReviewedHoverLiveAdmission::hex(body+39,32,supplied_recipe)||
       !ReviewedHoverLiveAdmission::hex(body+104,32,supplied_release)||
       !ReviewedHoverLiveAdmission::nonzero(boot,16)||
       !ReviewedHoverLiveAdmission::nonzero(release,32)||
       !ReviewedHoverLiveAdmission::equal(supplied_boot,boot,16)||
       !ReviewedHoverLiveAdmission::equal(supplied_release,release,32))return false;
    uint8_t calculated[32]{};
    if(!crypto.sha256(reinterpret_cast<const uint8_t*>(canonical),
                      sizeof(canonical)-1,calculated)||
       !ReviewedHoverLiveAdmission::equal(supplied_recipe,calculated,32))return false;
    std::memcpy(output.recipe_digest,calculated,32);return true;
  }
};
}
