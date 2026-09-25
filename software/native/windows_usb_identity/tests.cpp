#include "fake_api.h"
#include <algorithm>
#include <iostream>
#include <set>
using namespace rocell::usb_identity;
int main(int argc, char **argv) {
  try {
    const std::set<std::string> names = {"nominal",
                                         "unicode",
                                         "usb2",
                                         "pipes",
                                         "maximum-raw",
                                         "v2-unavailable",
                                         "no-serial",
                                         "duplicate-mapping",
                                         "changed-device",
                                         "malformed-device",
                                         "malformed-language",
                                         "malformed-serial",
                                         "language-conflict",
                                         "malformed-ex",
                                         "malformed-v2",
                                         "close-failure",
                                         "call-limit",
                                         "api-failure",
                                         "timeout",
                                         "cancelled",
                                         "byte-limit"};
    auto run = [](const std::string &name) {
      test::FakeApi api(name);
      auto r = test::request(name == "unicode");
      Limits limits;
      if (name == "byte-limit")
        limits.result_bytes = 18000;
      if (name == "call-limit")
        limits.calls = 20;
      std::uint64_t tick = 0;
      return observe_usb_identity(
          api, r, limits,
          [&] { return name == "cancelled" && api.invocations > 15; },
          [&] {
            if (name == "timeout")
              tick += 200;
            return tick;
          });
    };
    if (argc == 3 && std::string(argv[1]) == "--emit" && names.count(argv[2])) {
      std::cout << serialize_observation(run(argv[2])) << '\n';
      return 0;
    }
    if (argc == 2 && std::string(argv[1]) == "--request") {
      std::cout << test::request_json(test::request()) << '\n';
      return 0;
    }
    if (argc == 3 && std::string(argv[1]) == "--request" &&
        std::string(argv[2]) == "unicode") {
      std::cout << test::request_json(test::request(true)) << '\n';
      return 0;
    }
    if (argc != 1)
      return 2;
    unsigned assertions = 0;
    auto check = [&](bool ok) {
      ++assertions;
      if (!ok)
        throw std::runtime_error("Fake assertion " +
                                 std::to_string(assertions));
    };
    for (const auto &name : names) {
      auto o = run(name);
      auto json = serialize_observation(o);
      const bool complete = name == "nominal" || name == "unicode" ||
                            name == "usb2" || name == "pipes" ||
                            name == "v2-unavailable";
      check((o.outcome == "OBSERVED") == complete);
      check(json.size() <= 65536);
      check(o.calls.size() <= 128);
      if (!complete)
        check(o.error.has_value());
      if (complete)
        check(mapping_json(*o.pre) == mapping_json(*o.post));
      if (name == "no-serial")
        check(o.serials.empty() && !o.languages);
      if (name == "call-limit")
        check(o.error->code == "CALL_LIMIT");
      if (name == "maximum-raw") {
        check(o.error->code == "BYTE_LIMIT");
        check(json.find("\"returned_raw_hex\":\"01000000") !=
              std::string::npos);
      }
      if (name == "malformed-ex") {
        const auto found =
            std::find_if(o.calls.begin(), o.calls.end(), [](const Call &c) {
              return c.input.op == Op::ConnectionEx;
            });
        check(found != o.calls.end() && found->result.bytes.at(24) == 2);
        check(json.find("\"returned_raw_hex\":\"" + hex(found->result.bytes) +
                        "\"") != std::string::npos);
      }
      if (name == "close-failure") {
        unsigned closes = 0;
        for (const auto &c : o.calls)
          if (c.input.op == Op::CloseHub)
            ++closes;
        check(closes == 1);
      }
    }
    const auto r = test::request();
    AdmissionState gate(r, 31415, std::string(64, 'f'));
    const auto release =
        "{\"challenge_sha256\":\"" + sha256(std::string(64, 'f')) +
        "\",\"child_pid\":31415,\"permit_sha256\":\"" + r.permit() +
        "\",\"request_sha256\":\"" + r.hash +
        "\",\"schema\":\"rocell.native_usb_identity_admission_release.v1\"}";
    gate.accept(release, true);
    check(gate.admitted());
    try {
      gate.accept(release, true);
      check(false);
    } catch (const std::exception &) {
      check(true);
    }
    AdmissionState eof(r, 31415, std::string(64, 'f'));
    try {
      eof.accept(release, false);
      check(false);
    } catch (const std::exception &) {
      check(!eof.admitted());
    }
    std::cout
        << assertions
        << " incapable USB assertions passed; no Windows adapter linked\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
