import XCTest
@testable import SMCWriteLib

/// Mock SMC driver that records calls and returns configured results.
final class MockSMCDriver: SMCDriverProtocol {
    var openResult: Int32 = 0  // KERN_SUCCESS
    var closeCallCount = 0
    var openCallCount = 0
    var writeCallCount = 0
    var readCallCount = 0
    var lastWriteKey: String?
    var lastWriteData: [UInt8]?
    var writeResult: Int32 = 0
    var readResult: ([UInt8], Int32) = ([], 0)
    var isOpen = false

    func open() -> Int32 {
        openCallCount += 1
        if openResult == 0 { isOpen = true }
        return openResult
    }

    func close() {
        closeCallCount += 1
        isOpen = false
    }

    func writeKey(_ key: String, data: [UInt8]) -> Int32 {
        writeCallCount += 1
        lastWriteKey = key
        lastWriteData = data
        return writeResult
    }

    func readKey(_ key: String) -> ([UInt8], Int32) {
        readCallCount += 1
        return readResult
    }
}

final class CommandHandlerTests: XCTestCase {

    var mock: MockSMCDriver!
    var handler: CommandHandler!

    override func setUp() {
        super.setUp()
        mock = MockSMCDriver()
        handler = CommandHandler(driver: mock)
    }

    // MARK: - Ping

    func testPingReturnsOk() {
        let result = handler.handle(["cmd": "ping"])
        XCTAssertEqual(result["ok"] as? Bool, true)
        XCTAssertNotNil(result["version"])
    }

    // MARK: - Open

    func testOpenSuccess() {
        let result = handler.handle(["cmd": "open"])
        XCTAssertEqual(result["ok"] as? Bool, true)
        XCTAssertEqual(mock.openCallCount, 1)
    }

    func testOpenFailure() {
        mock.openResult = 1  // non-zero = failure
        let result = handler.handle(["cmd": "open"])
        XCTAssertEqual(result["ok"] as? Bool, false)
        XCTAssertNotNil(result["error"] as? String)
    }

    // MARK: - Close

    func testClose() {
        _ = handler.handle(["cmd": "open"])
        let result = handler.handle(["cmd": "close"])
        XCTAssertEqual(result["ok"] as? Bool, true)
        XCTAssertEqual(mock.closeCallCount, 1)
    }

    // MARK: - Write

    func testWriteSuccess() {
        _ = handler.handle(["cmd": "open"])
        let result = handler.handle([
            "cmd": "write",
            "key": "F0Mn",
            "data": "00409c45",
        ])
        XCTAssertEqual(result["ok"] as? Bool, true)
        XCTAssertEqual(mock.lastWriteKey, "F0Mn")
        XCTAssertEqual(mock.lastWriteData, [0x00, 0x40, 0x9c, 0x45])
    }

    func testWriteMissingKey() {
        _ = handler.handle(["cmd": "open"])
        let result = handler.handle(["cmd": "write", "data": "00"])
        XCTAssertEqual(result["ok"] as? Bool, false)
        XCTAssertTrue((result["error"] as? String)?.contains("key") ?? false)
    }

    func testWriteMissingData() {
        _ = handler.handle(["cmd": "open"])
        let result = handler.handle(["cmd": "write", "key": "F0Mn"])
        XCTAssertEqual(result["ok"] as? Bool, false)
        XCTAssertTrue((result["error"] as? String)?.contains("data") ?? false)
    }

    func testWriteInvalidHex() {
        _ = handler.handle(["cmd": "open"])
        let result = handler.handle([
            "cmd": "write",
            "key": "F0Mn",
            "data": "zzzz",
        ])
        XCTAssertEqual(result["ok"] as? Bool, false)
    }

    func testWriteKeyWrongLength() {
        _ = handler.handle(["cmd": "open"])
        let result = handler.handle([
            "cmd": "write",
            "key": "AB",
            "data": "00",
        ])
        XCTAssertEqual(result["ok"] as? Bool, false)
    }

    func testWriteSmcFailure() {
        _ = handler.handle(["cmd": "open"])
        mock.writeResult = 1  // simulate IOKit failure
        let result = handler.handle([
            "cmd": "write",
            "key": "F0Mn",
            "data": "00409c45",
        ])
        XCTAssertEqual(result["ok"] as? Bool, false)
    }

    func testWriteWithoutOpenFails() {
        let result = handler.handle([
            "cmd": "write",
            "key": "F0Mn",
            "data": "00409c45",
        ])
        XCTAssertEqual(result["ok"] as? Bool, false)
        XCTAssertTrue((result["error"] as? String)?.lowercased().contains("not open") ?? false)
    }

    // MARK: - Read

    func testReadSuccess() {
        _ = handler.handle(["cmd": "open"])
        mock.readResult = ([0x00, 0x40, 0x9c, 0x45], 0)
        let result = handler.handle(["cmd": "read", "key": "F0Mn"])
        XCTAssertEqual(result["ok"] as? Bool, true)
        XCTAssertEqual(result["data"] as? String, "00409c45")
    }

    func testReadMissingKey() {
        _ = handler.handle(["cmd": "open"])
        let result = handler.handle(["cmd": "read"])
        XCTAssertEqual(result["ok"] as? Bool, false)
    }

    // MARK: - Unknown / missing command

    func testUnknownCommand() {
        let result = handler.handle(["cmd": "foobar"])
        XCTAssertEqual(result["ok"] as? Bool, false)
    }

    func testMissingCommand() {
        let result = handler.handle(["hello": "world"])
        XCTAssertEqual(result["ok"] as? Bool, false)
    }
}
