// Include AFTER the pinned RoArm-M3 module. Uses its real elbow conversion with
// returnType=0 (no write), restoring the temporary shared target immediately.
// Bounds must come from reviewed trial admission; these scalar checks alone are
// NOT clearance, collision, freshness, or physical safety validation.
#pragma once
#include <math.h>
#include <stdint.h>
namespace rocell_diag {
struct ElbowAdmissionBounds {
  double minimum_rad,maximum_rad;
  uint16_t maximum_speed;
  uint8_t maximum_acceleration;
};
class ReferenceElbowAdmission {
 public:
  explicit ReferenceElbowAdmission(ElbowAdmissionBounds bounds):bounds_(bounds) {}
  bool admit_and_convert(double rad,uint16_t speed,uint8_t acceleration,uint16_t& target) {
    target=0;
    if(!isfinite(bounds_.minimum_rad)||!isfinite(bounds_.maximum_rad)||
       bounds_.minimum_rad<0 || bounds_.maximum_rad>M_PI ||
       bounds_.minimum_rad>bounds_.maximum_rad || !bounds_.maximum_speed ||
       !bounds_.maximum_acceleration || !isfinite(rad) || rad<bounds_.minimum_rad ||
       rad>bounds_.maximum_rad || !speed || speed>bounds_.maximum_speed ||
       !acceleration || acceleration>bounds_.maximum_acceleration)return false;
    const auto saved=goalPos[3];
    const int converted=RoArmM3_elbowJointCtrlRad(0,rad,speed,acceleration);
    goalPos[3]=saved;
    if(converted<1024 || converted>3071)return false;
    target=static_cast<uint16_t>(converted);return true;
  }
 private:
  const ElbowAdmissionBounds bounds_;
};
}
