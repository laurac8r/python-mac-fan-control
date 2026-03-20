import Foundation

/// Protocol abstracting SMC driver operations for testability.
public protocol SMCDriverProtocol: AnyObject {
    var isOpen: Bool { get }
    func open() -> Int32
    func close()
    func writeKey(_ key: String, data: [UInt8]) -> Int32
    func readKey(_ key: String) -> ([UInt8], Int32)
}
