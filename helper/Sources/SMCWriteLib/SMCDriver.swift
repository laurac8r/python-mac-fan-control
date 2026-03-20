import Foundation
import IOKit

/// SMC IOKit struct definitions matching the AppleSMC kernel driver layout.

private let KERNEL_INDEX_SMC: UInt32 = 2
private let SMC_CMD_READ_KEYINFO: UInt8 = 9
private let SMC_CMD_READ_BYTES: UInt8 = 5
private let SMC_CMD_WRITE_BYTES: UInt8 = 6

private struct SMCVersion {
    var major: CChar = 0
    var minor: CChar = 0
    var build: CChar = 0
    var reserved: CChar = 0
    var release: (UInt8, UInt8) = (0, 0)
}

private struct SMCPLimitData {
    var version: (UInt8, UInt8) = (0, 0)
    var length: (UInt8, UInt8) = (0, 0)
    var cpuPLimit: UInt32 = 0
    var gpuPLimit: UInt32 = 0
    var memPLimit: UInt32 = 0
}

private struct SMCKeyInfoData {
    var dataSize: UInt32 = 0
    var dataType: UInt32 = 0
    var dataAttributes: UInt8 = 0
}

private struct SMCKeyData {
    var key: UInt32 = 0
    var vers = SMCVersion()
    var pLimitData = SMCPLimitData()
    var keyInfo = SMCKeyInfoData()
    var result: UInt8 = 0
    var status: UInt8 = 0
    var data8: UInt8 = 0
    var data32: UInt32 = 0
    var bytes: (
        UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8,
        UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8,
        UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8,
        UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8, UInt8
    ) = (0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
}

/// Real IOKit-backed SMC driver. Requires macOS and appropriate privileges.
public final class SMCDriver: SMCDriverProtocol {
    private var connection: io_connect_t = 0
    public private(set) var isOpen = false

    public init() {}

    public func open() -> Int32 {
        if isOpen { return 0 }
        let matching = IOServiceMatching("AppleSMC")
        let service = IOServiceGetMatchingService(kIOMainPortDefault, matching)
        guard service != 0 else { return 1 }
        let kr = IOServiceOpen(service, mach_task_self_, 0, &connection)
        IOObjectRelease(service)
        if kr == KERN_SUCCESS { isOpen = true }
        return kr
    }

    public func close() {
        if isOpen {
            IOServiceClose(connection)
            connection = 0
            isOpen = false
        }
    }

    public func writeKey(_ key: String, data: [UInt8]) -> Int32 {
        let (dataSize, dataType, infoKr) = readKeyInfo(key)
        guard infoKr == KERN_SUCCESS, dataSize > 0 else { return infoKr != 0 ? infoKr : 1 }

        var input = SMCKeyData()
        input.key = fourCharCode(key)
        input.data8 = SMC_CMD_WRITE_BYTES
        input.keyInfo.dataSize = dataSize
        input.keyInfo.dataType = dataType

        withUnsafeMutablePointer(to: &input.bytes) { ptr in
            ptr.withMemoryRebound(to: UInt8.self, capacity: 32) { buf in
                for i in 0..<min(data.count, 32) {
                    buf[i] = data[i]
                }
            }
        }

        var output = SMCKeyData()
        let inputSize = MemoryLayout<SMCKeyData>.stride
        var outputSize = MemoryLayout<SMCKeyData>.stride
        return IOConnectCallStructMethod(
            connection, KERNEL_INDEX_SMC,
            &input, inputSize,
            &output, &outputSize
        )
    }

    public func readKey(_ key: String) -> ([UInt8], Int32) {
        let (dataSize, _, infoKr) = readKeyInfo(key)
        guard infoKr == KERN_SUCCESS, dataSize > 0 else { return ([], infoKr != 0 ? infoKr : 1) }

        var input = SMCKeyData()
        var output = SMCKeyData()
        input.key = fourCharCode(key)
        input.keyInfo.dataSize = dataSize
        input.data8 = SMC_CMD_READ_BYTES

        let inputSize = MemoryLayout<SMCKeyData>.stride
        var outputSize = MemoryLayout<SMCKeyData>.stride
        let kr = IOConnectCallStructMethod(
            connection, KERNEL_INDEX_SMC,
            &input, inputSize,
            &output, &outputSize
        )

        var result = [UInt8]()
        withUnsafePointer(to: &output.bytes) { ptr in
            ptr.withMemoryRebound(to: UInt8.self, capacity: 32) { buf in
                for i in 0..<Int(dataSize) {
                    result.append(buf[i])
                }
            }
        }
        return (result, kr)
    }

    deinit { close() }

    // MARK: - Private

    private func readKeyInfo(_ key: String) -> (size: UInt32, type: UInt32, kern_return_t) {
        var input = SMCKeyData()
        var output = SMCKeyData()
        input.key = fourCharCode(key)
        input.data8 = SMC_CMD_READ_KEYINFO

        let inputSize = MemoryLayout<SMCKeyData>.stride
        var outputSize = MemoryLayout<SMCKeyData>.stride
        let kr = IOConnectCallStructMethod(
            connection, KERNEL_INDEX_SMC,
            &input, inputSize,
            &output, &outputSize
        )
        return (output.keyInfo.dataSize, output.keyInfo.dataType, kr)
    }
}
