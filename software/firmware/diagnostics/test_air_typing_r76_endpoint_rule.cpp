#include "air_typing_r76_endpoint_rule.h"
#include <cassert>
using rocell_diag::air_typing_r76_endpoint_joint_verified;
int main(){
  // Leg 9: shoulder pair started essentially on the new targets.
  assert(air_typing_r76_endpoint_joint_verified(2076,2082,2080,2082));
  assert(air_typing_r76_endpoint_joint_verified(2038,2033,2034,2033));
  // Non-moving but far from target remains a failure.
  assert(!air_typing_r76_endpoint_joint_verified(2076,2088,2080,2088));
  // A large command cannot claim success by mere goal readback.
  assert(!air_typing_r76_endpoint_joint_verified(1994,2001,1941,2001));
  assert(air_typing_r76_endpoint_joint_verified(1994,2001,1941,1949));
  assert(!air_typing_r76_endpoint_joint_verified(1994,2001,1941,2004));
  assert(!air_typing_r76_endpoint_joint_verified(1994,2001,1941,1920));
}
