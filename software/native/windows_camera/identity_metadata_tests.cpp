// All resolver calls use FakeApi below. Never instantiate/invoke the production
// WindowsIdentityMetadataApi in this executable, enumerate devices or touch files.
#include "identity_metadata.h"
#include <iostream>
#include <map>
#include <stdexcept>

using namespace rocell::identity;
namespace {
unsigned passed = 0;
void check(bool condition, const char* name) {
  if (!condition) throw std::runtime_error(name);
  ++passed;
}
Error missing() { return {Unavailable::ApiFailure, ErrorDomain::ConfigurationManager, 13}; }
RawProperty locations(const std::vector<std::wstring>& paths) {
  RawProperty raw; raw.property_type = kStringListPropertyType;
  for (const auto& path : paths) {
    for (wchar_t c : path) {
      raw.bytes.push_back(static_cast<std::uint8_t>(c & 255));
      raw.bytes.push_back(static_cast<std::uint8_t>((c >> 8) & 255));
    }
    raw.bytes.insert(raw.bytes.end(), {0, 0});
  }
  raw.bytes.insert(raw.bytes.end(), {0, 0});
  if (paths.empty()) raw.bytes.insert(raw.bytes.end(), {0, 0});
  return raw;
}
RawProperty container() {
  return {kGuidPropertyType, {0x78, 0x56, 0x34, 0x12, 0xbc, 0x9a, 0xf0, 0xde,
      1, 2, 3, 4, 5, 6, 7, 8}};
}
RawProperty driver_string(const std::wstring& value) {
  auto raw = locations({value});
  raw.property_type = kStringPropertyType;
  raw.bytes.resize(raw.bytes.size() - 2);
  return raw;
}

class FakeApi final : public IdentityMetadataApi {
public:
  unsigned calls = 0, parent_calls = 0;
  std::wstring supplied_endpoint;
  EndpointMapping mapping;
  Observation<DevNode> root = Observation<DevNode>::observed_value(3);
  std::map<DevNode, DevNode> parents{{1, 2}, {2, 3}};
  std::map<DevNode, std::wstring> instances{{1, L"USB\\FIXTURE_CAMERA\\uninterpreted-suffix"},
      {2, L"USB\\FIXTURE_PARENT"}, {3, L"HTREE\\FIXTURE_ROOT"}};
  std::map<DevNode, RawProperty> containers{{1, container()}};
  std::map<DevNode, RawProperty> paths{{1, locations({L"PCIROOT(FIXTURE)#USBROOT(0)#USB(2)", L"fixture-alt"})}};
  std::map<std::pair<DevNode, Property>, RawProperty> drivers{
    {{1, Property::DriverProvider}, driver_string(L"FIXTURE provider")},
    {{1, Property::DriverService}, driver_string(L"FIXTURE service")},
    {{1, Property::DriverVersion}, driver_string(L"1.2.3.4")},
    {{1, Property::DriverInfPath}, driver_string(L"fixture.inf")},
  };
  std::vector<std::pair<DevNode, Property>> driver_queries;
  bool throw_on_any_call = false;
  std::function<void()> on_call;
  FakeApi() {
    mapping.devnode = Observation<DevNode>::observed_value(1);
    mapping.interface_path = Observation<std::wstring>::observed_value(L"opaque-SYNTHETIC-endpoint");
  }
  void called() {
    if (throw_on_any_call) throw std::runtime_error("unexpected API invocation");
    ++calls;
    if (on_call) on_call();
  }
  EndpointMapping map_endpoint(const std::wstring& endpoint) override {
    called(); supplied_endpoint = endpoint; return mapping;
  }
  Observation<std::wstring> instance_id(DevNode node, std::uint32_t) override {
    called(); const auto found = instances.find(node);
    return found == instances.end() ? Observation<std::wstring>::missing(missing()) : Observation<std::wstring>::observed_value(found->second);
  }
  Observation<RawProperty> property(DevNode node, Property key, std::uint32_t) override {
    called();
    if (key != Property::ContainerId && key != Property::LocationPaths) {
      driver_queries.emplace_back(node, key);
      const auto found = drivers.find({node, key});
      return found == drivers.end() ? Observation<RawProperty>::missing(missing()) : Observation<RawProperty>::observed_value(found->second);
    }
    const auto& values = key == Property::ContainerId ? containers : paths;
    const auto found = values.find(node);
    return found == values.end() ? Observation<RawProperty>::missing(missing()) : Observation<RawProperty>::observed_value(found->second);
  }
  Observation<DevNode> root_node() override { called(); return root; }
  Observation<DevNode> parent_node(DevNode node) override {
    called(); ++parent_calls; const auto found = parents.find(node);
    return found == parents.end() ? Observation<DevNode>::missing(missing()) : Observation<DevNode>::observed_value(found->second);
  }
};
RunControl control() { return {[]() { return std::uint64_t{100}; }, []() { return false; }}; }
IdentityMetadata run(FakeApi& api, Limits limits = {}) {
  return resolve_identity_metadata(api, L"opaque-SYNTHETIC-endpoint", limits, control());
}

void test_property_parsers() {
  const auto guid = decode_container_guid(container());
  check(guid.observed() && guid.value->data1 == 0x12345678 && guid.value->data2 == 0x9abc &&
      guid.value->data3 == 0xdef0 && guid.value->data4[7] == 8, "GUID little-endian fields");
  auto raw = container(); raw.bytes.pop_back();
  check(!decode_container_guid(raw).observed(), "GUID malformed length refused");
  raw = container(); raw.property_type = kStringListPropertyType;
  check(decode_container_guid(raw).unavailable.reason == Unavailable::WrongPropertyType, "GUID wrong type refused");
  const auto zero_guid = decode_container_guid({kGuidPropertyType, std::vector<std::uint8_t>(16, 0)});
  check(zero_guid.observed() && zero_guid.value->data1 == 0, "zero GUID retained as observation, not a manufactured identity");
  const auto decoded = decode_location_paths(locations({L"PORT-A", L"PORT-B"}), 16, 1024);
  check(decoded.observed() && decoded.value->size() == 2 && decoded.value->at(1) == L"PORT-B", "MULTI_SZ observes two paths");
  check(decode_location_paths(locations({}), 16, 1024).value->empty(), "empty MULTI_SZ remains empty observation");
  raw = locations({L"PORT-A"}); raw.bytes.pop_back();
  check(!decode_location_paths(raw, 16, 1024).observed(), "odd UTF-16 byte count refused");
  raw = locations({L"PORT-A"}); raw.bytes.resize(raw.bytes.size() - 2);
  check(!decode_location_paths(raw, 16, 1024).observed(), "missing double terminator refused");
  raw = locations({L"PORT-A", L"", L"PORT-B"});
  check(!decode_location_paths(raw, 16, 1024).observed(), "interior empty MULTI_SZ refused");
  check(decode_location_paths(locations({L"PORT-A", L"PORT-B"}), 1, 1024).unavailable.reason == Unavailable::ByteLimit, "path count budget");
  check(decode_location_paths(locations({L"PORT-A"}), 16, 3).unavailable.reason == Unavailable::ByteLimit, "path character budget");
  check(!decode_location_paths(locations({std::wstring(1, wchar_t(0xd800))}), 16, 1024).observed(), "unpaired UTF-16 surrogate refused");
}

void test_nominal_and_missing() {
  FakeApi api;
  check(api.calls == 0, "fake construction inert");
  const auto result = run(api);
  check(api.supplied_endpoint == L"opaque-SYNTHETIC-endpoint", "opaque endpoint passed unchanged");
  check(result.device && result.device->instance_id.observed() &&
      result.device->instance_id.value->find(L"uninterpreted-suffix") != std::wstring::npos,
      "instance ID observed whole without inferred serial");
  check(result.device->container_id.observed() && result.device->location_paths.observed(), "selected node typed properties");
  check(result.parents.size() == 2 && result.parents[0].devnode == 2 && result.parents[1].devnode == 3,
      "parent chain order");
  check(result.chain_end == ChainEnd::ReachedObservedRoot && api.parent_calls == 2,
      "observed root ends chain without failed-parent inference");
  check(!result.parents[0].container_id.observed() && result.parents[0].container_id.unavailable.domain == ErrorDomain::ConfigurationManager,
      "missing property retains API code/domain");
  check(result.api_calls == api.calls && !result.physical_authority, "bounded metadata counts and no authority");

  FakeApi absent;
  absent.mapping.devnode = Observation<DevNode>::missing({Unavailable::ApiFailure, ErrorDomain::Win32, 433});
  const auto not_found = run(absent);
  check(!not_found.device && not_found.parents.empty() && absent.calls == 1, "removed endpoint stops with no fallback");

  FakeApi removed;
  removed.parents.clear();
  const auto stopped = run(removed);
  check(stopped.chain_end == ChainEnd::ParentUnavailable && stopped.chain_error.native_code == 13,
      "missing parent is not claimed to be root");

  FakeApi no_root;
  no_root.root = Observation<DevNode>::missing(missing());
  check(run(no_root).chain_end == ChainEnd::ParentUnavailable, "unavailable root observation remains incomplete");

  FakeApi cleanup;
  cleanup.mapping.cleanup_errors.push_back({Unavailable::ApiFailure, ErrorDomain::Win32, 5});
  check(run(cleanup).mapping.cleanup_errors.size() == 1, "metadata cleanup failure retained");

  FakeApi selected_second;
  selected_second.mapping.devnode = Observation<DevNode>::observed_value(2);
  check(run(selected_second).device->devnode == 2, "resolved devnode used rather than an enumeration index");
}

void test_bounds_and_faults() {
  FakeApi cycle; cycle.parents[2] = 1;
  check(run(cycle).chain_end == ChainEnd::ParentCycle && cycle.parent_calls == 2, "cycle cannot loop");
  FakeApi depth; Limits one; one.max_parent_nodes = 1;
  check(run(depth, one).chain_end == ChainEnd::DepthLimit && depth.parent_calls == 1, "depth budget enforced");
  FakeApi malformed; malformed.paths[1] = {kGuidPropertyType, {1, 2, 3}};
  check(run(malformed).device->location_paths.unavailable.reason == Unavailable::WrongPropertyType, "wrong property type is not converted");
  FakeApi huge; huge.paths[1] = {kStringListPropertyType, std::vector<std::uint8_t>(32 * 1024, 0)};
  check(run(huge).device->location_paths.unavailable.reason == Unavailable::ByteLimit, "oversized API property refused");
  FakeApi quota; Limits limited; limited.max_property_bytes = 16; limited.max_total_property_bytes = 16;
  const auto quota_result = run(quota, limited);
  check(quota_result.observed_property_bytes == 16 && quota_result.device->location_paths.unavailable.reason == Unavailable::ByteLimit,
      "total byte budget stops additional property reads");
  FakeApi bad_instance; bad_instance.instances[1] = std::wstring(L"bad\0suffix", 10);
  check(!run(bad_instance).device->instance_id.observed(), "embedded-NUL instance ID refused");
  FakeApi cancelled; cancelled.throw_on_any_call = true;
  const auto cancelled_result = resolve_identity_metadata(cancelled, L"fixture", Limits{},
      {[]() { return std::uint64_t{100}; }, []() { return true; }});
  check(cancelled_result.chain_end == ChainEnd::Cancelled && cancelled.calls == 0, "pre-cancel means no metadata queries");
  FakeApi deadline; std::uint64_t tick = 0;
  const auto timed = resolve_identity_metadata(deadline, L"fixture", Limits{},
      {[&]() { tick += 5001; return tick; }, []() { return false; }});
  check(timed.chain_end == ChainEnd::Deadline && deadline.calls == 0, "deadline before first API query");
  FakeApi cancelled_later; bool cancelled_flag = false;
  cancelled_later.on_call = [&]() { if (cancelled_later.calls == 4) cancelled_flag = true; };
  const auto later = resolve_identity_metadata(cancelled_later, L"fixture", Limits{},
      {[]() { return std::uint64_t{100}; }, [&]() { return cancelled_flag; }});
  check(later.chain_end == ChainEnd::Cancelled && cancelled_later.calls == 4, "mid-query cancellation never renews");
  FakeApi backwards; unsigned clocks = 0;
  const auto bad_clock = resolve_identity_metadata(backwards, L"fixture", Limits{},
      {[&]() { return std::uint64_t{++clocks == 1 ? 100u : 99u}; }, []() { return false; }});
  check(bad_clock.chain_end == ChainEnd::ClockChanged && backwards.calls == 0, "backward clock is not accepted");
  FakeApi untouched; untouched.throw_on_any_call = true; bool rejected = false;
  try { resolve_identity_metadata(untouched, std::wstring(L"bad\0endpoint", 12), Limits{}, control()); }
  catch (const std::invalid_argument&) { rejected = true; }
  check(rejected && untouched.calls == 0, "malformed endpoint stops before API seam");
  rejected = false; Limits excessive; excessive.max_parent_nodes = 17;
  try { run(untouched, excessive); } catch (const std::invalid_argument&) { rejected = true; }
  check(rejected && untouched.calls == 0, "invalid policy budget is not weakened");
}

void test_driver_properties() {
  check(decode_driver_string(driver_string(L"Provider \u00e9 \U0001f600"), 1024).observed(), "driver UTF-16 round trip");
  auto raw = driver_string(L"driver"); raw.property_type = kStringListPropertyType;
  check(decode_driver_string(raw, 1024).unavailable.reason == Unavailable::WrongPropertyType, "driver type not coerced");
  raw = driver_string(L"driver"); raw.bytes.pop_back();
  check(!decode_driver_string(raw, 1024).observed(), "odd driver bytes refused");
  raw = driver_string(L"driver"); raw.bytes.resize(raw.bytes.size() - 2);
  check(!decode_driver_string(raw, 1024).observed(), "unterminated driver refused");
  check(!decode_driver_string(driver_string(L""), 1024).observed(), "empty driver not invented");
  check(!decode_driver_string(driver_string(std::wstring(L"a\0b", 3)), 1024).observed(), "embedded NULL driver refused");
  check(!decode_driver_string(driver_string(std::wstring(1, wchar_t(0xd800))), 1024).observed(), "malformed surrogate refused");
  check(decode_driver_string(driver_string(std::wstring(1025, L'x')), 1024).unavailable.reason == Unavailable::ByteLimit, "driver UTF-16 bound");
  FakeApi api;
  const auto result = run(api);
  check(result.driver && result.driver->devnode == 1 && result.driver->provider.value == L"FIXTURE provider" &&
      result.driver->service.value == L"FIXTURE service" && result.driver->version.value == L"1.2.3.4" &&
      result.driver->inf_path.value == L"fixture.inf", "four exact endpoint driver observations");
  check(api.driver_queries == std::vector<std::pair<DevNode, Property>>{
      {1, Property::DriverProvider}, {1, Property::DriverService}, {1, Property::DriverVersion}, {1, Property::DriverInfPath}},
      "closed driver order and no ancestor queries");
  FakeApi missing_driver;
  missing_driver.drivers.erase({1, Property::DriverProvider});
  missing_driver.drivers[{2, Property::DriverProvider}] = driver_string(L"ancestor cannot substitute");
  const auto partial = run(missing_driver);
  check(!partial.driver->provider.observed() && partial.driver->provider.unavailable.native_code == 13 &&
      partial.driver->service.observed(), "missing endpoint property never uses present parent or hides later fields");
  FakeApi removed;
  removed.on_call = [&]() { if (removed.calls == 5) removed.drivers.clear(); };
  const auto disappeared = run(removed);
  check(!disappeared.driver->provider.observed() && !disappeared.driver->inf_path.observed(), "disappeared driver stays unavailable");
  FakeApi huge;
  huge.drivers[{1, Property::DriverProvider}] = {kStringPropertyType, std::vector<std::uint8_t>(32 * 1024, 0)};
  check(run(huge).driver->provider.unavailable.reason == Unavailable::ByteLimit, "driver individual raw byte bound");
  FakeApi quota; Limits limited; limited.max_property_bytes = 16; limited.max_total_property_bytes = 16;
  const auto exhausted = run(quota, limited);
  check(exhausted.driver->provider.unavailable.reason == Unavailable::ByteLimit && quota.driver_queries.empty(),
      "driver shares original raw byte budget without querying past exhaustion");
  FakeApi wrong; wrong.mapping.interface_path = Observation<std::wstring>::observed_value(L"different-endpoint");
  check(run(wrong).driver->provider.unavailable.reason == Unavailable::NotRequested && wrong.driver_queries.empty(),
      "nonmatching endpoint cannot issue driver queries");
  FakeApi cleanup; cleanup.mapping.cleanup_errors.push_back({Unavailable::ApiFailure, ErrorDomain::Win32, 5});
  check(run(cleanup).driver->provider.unavailable.reason == Unavailable::NotRequested && cleanup.driver_queries.empty(),
      "failed mapping cleanup prevents driver queries");
  FakeApi late; std::uint64_t now = 100;
  late.on_call = [&]() { if (late.calls == 6) now += 5000; };
  const auto timed = resolve_identity_metadata(late, L"opaque-SYNTHETIC-endpoint", Limits{},
      {[&]() { return now; }, []() { return false; }});
  check(timed.chain_end == ChainEnd::Deadline && timed.driver->service.observed() &&
      timed.driver->version.unavailable.reason == Unavailable::NotRequested && late.calls == 6,
      "partial driver observations survive deadline without renewal");
}

void test_wire_serialization() {
  FakeApi api;
  auto result = run(api);
  const auto wire = serialize_identity_metadata(result, Limits{});
  check(wire.find("\"schema\":\"rocell.windows_camera_identity.v2\"") != std::string::npos,
      "identity uses a separate registered receipt version");
  check(wire.find("12345678-9abc-def0-0102-030405060708") != std::string::npos,
      "container GUID wire byte order");
  check(wire.find("\"availability\":\"UNAVAILABLE\",\"value\":null") != std::string::npos,
      "unavailable observations have no manufactured value");
  check(wire.find("\"camera_activation_count\":0,\"physical_authority\":false") != std::string::npos,
      "wire metadata never claims camera authority");
  result.requested_endpoint = L"quote\"backslash\\unicode-\u00e9-\U0001f600";
  const auto unicode = serialize_identity_metadata(result, Limits{});
  check(unicode.find("quote\\\"backslash\\\\unicode-\xc3\xa9-\xf0\x9f\x98\x80") != std::string::npos,
      "JSON escaping and UTF-16 surrogate pair encoding");
  result.parents.assign(1000, *result.device);
  bool rejected = false;
  try { serialize_identity_metadata(result, Limits{}); } catch (const std::runtime_error&) { rejected = true; }
  check(rejected, "serialized receipt byte ceiling");
}

void emit_fixtures() {
  // This executable has no path that calls WindowsIdentityMetadataApi. Emit
  // real serializer output from fake nodes for Python cross-language tests.
  bool first = true;
  std::cout << '[';
  auto emit = [&](const IdentityMetadata& result, Limits limits = {}) {
    if (!first) std::cout << ',';
    first = false;
    std::cout << serialize_identity_metadata(result, limits);
  };
  FakeApi nominal; emit(run(nominal));
  FakeApi absent;
  absent.mapping.devnode = Observation<DevNode>::missing({Unavailable::ApiFailure, ErrorDomain::Win32, 433});
  absent.mapping.interface_path = Observation<std::wstring>{};
  emit(run(absent));
  FakeApi cycle; cycle.parents[2] = 1; emit(run(cycle));
  FakeApi depth; Limits no_parents; no_parents.max_parent_nodes = 0; emit(run(depth, no_parents), no_parents);
  FakeApi removed; removed.parents.clear(); emit(run(removed));
  FakeApi no_root; no_root.root = Observation<DevNode>::missing(missing()); emit(run(no_root));
  FakeApi cleanup; cleanup.mapping.cleanup_errors.push_back({Unavailable::ApiFailure, ErrorDomain::Win32, 5}); emit(run(cleanup));
  FakeApi empty; empty.containers[1] = {kGuidPropertyType, std::vector<std::uint8_t>(16, 0)};
  empty.paths[1] = locations({}); emit(run(empty));
  // Every seam boundary through nominal completion: cancellations must retain
  // only completed observations and must never accidentally require a retry.
  for (unsigned boundary = 0; boundary <= 17; ++boundary) {
    FakeApi cancelled;
    emit(resolve_identity_metadata(cancelled, L"opaque-SYNTHETIC-endpoint", Limits{},
        {[]() { return std::uint64_t{100}; }, [&]() { return cancelled.calls >= boundary; }}));
  }
  FakeApi missing_driver; missing_driver.drivers.erase({1, Property::DriverProvider});
  missing_driver.drivers[{2, Property::DriverProvider}] = driver_string(L"not the endpoint driver"); emit(run(missing_driver));
  FakeApi wrong_type; wrong_type.drivers[{1, Property::DriverVersion}] = locations({L"not string"}); emit(run(wrong_type));
  FakeApi malformed; malformed.drivers[{1, Property::DriverInfPath}] = driver_string(std::wstring(1, wchar_t(0xd800))); emit(run(malformed));
  FakeApi huge; huge.drivers[{1, Property::DriverProvider}] = {kStringPropertyType, std::vector<std::uint8_t>(32 * 1024, 0)}; emit(run(huge));
  FakeApi wrong_endpoint; wrong_endpoint.mapping.interface_path = Observation<std::wstring>::observed_value(L"different-endpoint"); emit(run(wrong_endpoint));
  std::cout << "]\n";
}
} // namespace

int main(int argc, char** argv) {
  try {
    if (argc == 2 && std::string(argv[1]) == "--emit-fixtures") { emit_fixtures(); return 0; }
    if (argc != 1) throw std::invalid_argument("Only the registered pure fixture action is supported");
    test_property_parsers(); test_nominal_and_missing(); test_bounds_and_faults(); test_driver_properties(); test_wire_serialization();
    std::cout << "PASS: " << passed << " pure injected identity metadata assertions; Windows metadata API invocations: 0\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "FAIL: " << error.what() << '\n';
    return 1;
  }
}
