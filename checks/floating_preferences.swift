import Foundation

@main
struct FloatingPreferencesCheck {
    static func main() throws {
        var value = FloatingPreferences()
        assert(value.isValid && value.autoHide)
        value.taskMode = "manual"; value.taskIDs = ["one", "two"]; value.autoHide = false
        let data = try JSONEncoder().encode(value)
        let restored = try JSONDecoder().decode(FloatingPreferences.self, from: data)
        assert(restored.taskIDs == ["one", "two"] && !restored.autoHide)
        value.taskIDs = ["one", "one"]; assert(!value.isValid)
        value.taskIDs = ["<bad>"]; assert(!value.isValid)
        value.taskIDs = ["a", "b", "c", "d", "e"]; assert(!value.isValid)
        value.taskIDs = []; value.edge = "bad"; assert(!value.isValid)
        print("PASS: native preference validation and JSON round-trip")
    }
}
