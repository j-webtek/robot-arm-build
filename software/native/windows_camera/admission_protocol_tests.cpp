#include "admission_protocol.h"
#include <iostream>
#include <stdexcept>

using namespace rocell::admission;
namespace {
unsigned checks = 0;
void check(bool value) { ++checks; if (!value) throw std::runtime_error("ASSERTION_FAILED"); }
template<class F> void denied(F operation) { bool rejected = false; try { operation(); } catch (const std::exception&) { rejected = true; } check(rejected); }
std::string request_json() {
  const std::string h(64, 'a');
  return "{\"admission_timeout_ms\":2000,\"attempt_id\":\"attempt-1\",\"camera_request_sha256\":\"" + h + "\",\"endpoint\":\"explicit-incapable-endpoint\",\"endpoint_sha256\":\"" + sha256("explicit-incapable-endpoint") + "\",\"helper_sha256\":\"" + h + "\",\"native_duration_ms\":5000,\"operation_sha256\":\"" + h + "\",\"permit_sha256\":\"" + h + "\",\"runtime_registration_sha256\":\"" + h + "\",\"schema\":\"rocell.native_camera_admission_request.v1\",\"selected_identity_sha256\":\"" + h + "\",\"session_id\":\"session-1\",\"source_sha256\":\"" + h + "\"}";
}
std::string release_json(const Request& request, const std::string& challenge) {
  return "{\"challenge_sha256\":\"" + sha256(challenge) + "\",\"child_pid\":123,\"permit_sha256\":\"" + request.permit() + "\",\"request_sha256\":\"" + request.hash + "\",\"schema\":\"rocell.native_camera_admission_release.v1\"}";
}
}
int main() {
  try {
    check(sha256("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    const auto payload = request_json(); const auto request = parse_request(payload, sha256(payload));
    check(request.endpoint() == "explicit-incapable-endpoint");
    const std::string challenge(64, 'b');
    AdmissionState state(request, 123, challenge);
    check(!state.admitted()); check(parse_flat(state.ready(), handshake_limit).at("child_pid").text == "123");
    const auto release = release_json(request, challenge); state.accept(release, true); check(state.admitted());
    denied([&] { state.accept(release, true); });
    AdmissionState missing_eof(request, 123, challenge);
    denied([&] { missing_eof.accept(release, false); }); check(!missing_eof.admitted());
    denied([&] { missing_eof.accept(release, true); });
    denied([&] { parse_request(payload, std::string(64, '0')); });
    for (const auto& bad : {std::string("{}"), payload + "\n", payload + "x", std::string(16384, 'x')}) denied([&] { parse_request(bad, sha256(bad)); });
    for (const auto& bad : {"{\"a\":true}", "{\"a\":-1}", "{\"a\":1.0}", "{\"a\":01}", "{\"a\":1,\"a\":2}", "{\"b\":1,\"a\":2}", "{\"a\":{}}", "{\"a\":\"\\u0041\"}", "{\"a\":\"\\ud800\"}", "{\"a\":\"\\udc00\"}"}) denied([&] { parse_flat(bad, request_limit); });
    check(parse_flat("{\"a\":\"\\u00e9\"}", request_limit).at("a").text == std::string("\xc3\xa9"));
    check(parse_flat("{\"a\":\"\\ud83d\\ude00\"}", request_limit).at("a").text == std::string("\xf0\x9f\x98\x80"));
    auto changed = release; changed.replace(changed.find("123"), 3, "124"); denied([&] { validate_release(changed, request, 123, challenge); });
    denied([&] { validate_release(release, request, 123, std::string(64, 'c')); });
    denied([&] { validate_release(release + "\n", request, 123, challenge); });
    std::cout << "incapable admission parser assertions=" << checks << "; device APIs linked=0\n";
    return 0;
  } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
