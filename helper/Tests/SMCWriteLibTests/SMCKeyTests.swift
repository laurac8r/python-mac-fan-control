import XCTest
@testable import SMCWriteLib

final class SMCKeyTests: XCTestCase {

    // MARK: - fourCharCode

    func testFourCharCodeAppleSMC() {
        // "F0Mn" = 0x46304D6E
        let code = fourCharCode("F0Mn")
        XCTAssertEqual(code, 0x46304D6E)
    }

    func testFourCharCodeFNum() {
        // "FNum" = 0x464E756D
        let code = fourCharCode("FNum")
        XCTAssertEqual(code, 0x464E756D)
    }

    func testFourCharCodeTC0P() {
        // "TC0P" = 0x54433050
        let code = fourCharCode("TC0P")
        XCTAssertEqual(code, 0x54433050)
    }

    func testFourCharCodeOnlyUsesFirst4Chars() {
        // "F0MnX" should produce the same result as "F0Mn"
        let code = fourCharCode("F0MnExtra")
        XCTAssertEqual(code, fourCharCode("F0Mn"))
    }

    // MARK: - uint32ToString

    func testUint32ToStringF0Mn() {
        XCTAssertEqual(uint32ToString(0x46304D6E), "F0Mn")
    }

    func testUint32ToStringFNum() {
        XCTAssertEqual(uint32ToString(0x464E756D), "FNum")
    }

    // MARK: - Round trip

    func testRoundTrip() {
        for key in ["F0Mn", "F0Ac", "TC0P", "FNum", "flt ", "#KEY"] {
            XCTAssertEqual(uint32ToString(fourCharCode(key)), key, "Round-trip failed for '\(key)'")
        }
    }
}
