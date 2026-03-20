import XCTest
@testable import SMCWriteLib

final class HexUtilsTests: XCTestCase {

    // MARK: - hexToBytes

    func testHexToBytesEmpty() {
        XCTAssertEqual(hexToBytes(""), [])
    }

    func testHexToBytesSimple() {
        XCTAssertEqual(hexToBytes("00"), [0x00])
    }

    func testHexToBytesFourBytes() {
        XCTAssertEqual(hexToBytes("00409c45"), [0x00, 0x40, 0x9c, 0x45])
    }

    func testHexToBytesUppercase() {
        XCTAssertEqual(hexToBytes("FF"), [0xFF])
    }

    func testHexToBytesMixedCase() {
        XCTAssertEqual(hexToBytes("aAbB"), [0xAA, 0xBB])
    }

    func testHexToBytesOddLengthReturnsNil() {
        XCTAssertNil(hexToBytes("abc"))
    }

    func testHexToBytesInvalidCharsReturnsNil() {
        XCTAssertNil(hexToBytes("zz"))
    }

    // MARK: - bytesToHex

    func testBytesToHexEmpty() {
        XCTAssertEqual(bytesToHex([]), "")
    }

    func testBytesToHexSimple() {
        XCTAssertEqual(bytesToHex([0x00, 0x40, 0x9c, 0x45]), "00409c45")
    }

    func testBytesToHexFF() {
        XCTAssertEqual(bytesToHex([0xFF]), "ff")
    }
}
