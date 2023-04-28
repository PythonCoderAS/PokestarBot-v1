Convert a number from a base to another base.

Arguments:
* `base_from`: The base to convert from. Allows any numerical base from 2 to 36.
* `base_to`: The base to convert to.
* `number`: The number to convert. Multiple numbers can be separated using spaces.

Base Format:
* `<number>`: An integer value representing the base.
* `binary` / `bin` / `basetwo` / `base2`: Binary number system, or base 2.
* `int` / `integer` / `decimal` / `baseten` / `base10`: Decimal number system, or base 10.
* `hex` / `hexadecimal` / `basesixteen` / `base16`: Hexadecimal number system, or base 16,

Number Format:
* Binary Number Format: `XXXXXX` / `0bXXXXXX` where `X` is either `0` or `1`.
* Decimal Number Format: `XXXXXX` where `X` is a number between (and including) `0` and `9`.
* Hexadecimal Number Format: `XXXXXX` / `0cXXXXXX` where `X` is a number between (and including) `0` and `9` or one of the letters `A`, `B`, `C`, `D`, `E`, `F` (case insensitive).

Examples:
* `{prefix}convert 2 10 111111`
* `{prefix}convert 2 10 0b111111`
* `{prefix}convert 10 2 14`
* `{prefix}convert 16 2 AB23`
* `{prefix}convert 16 2 0xAB23`
* `{prefix}convert 2 10 111111 0b111101`
