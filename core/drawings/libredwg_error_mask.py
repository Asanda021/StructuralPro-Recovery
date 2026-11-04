"""Read-only LibreDWG C-API bitmask diagnosis; never grants CAD/takeoff approval.

A CLI return code is not the dwg_read_file() C-API error mask.  In particular
LibreDWG may return CLI 0/SUCCESS after accumulating noncritical read flags.
Keep both observations distinct.  The diagnostic does not decode proprietary
MAP/AEC payloads or infer causes from a combined mask.

Reference: LibreDWG dwg.h Dwg_Error enum and GNU LibreDWG Errors manual.
"""
from __future__ import annotations

from typing import Any

_ERROR_FLAGS = (
    (1, "DWG_ERR_WRONGCRC"),
    (2, "DWG_ERR_NOTYETSUPPORTED"),
    (4, "DWG_ERR_UNHANDLEDCLASS"),
    (8, "DWG_ERR_INVALIDTYPE"),
    (16, "DWG_ERR_INVALIDHANDLE"),
    (32, "DWG_ERR_INVALIDEED"),
    (64, "DWG_ERR_VALUEOUTOFBOUNDS"),
    (128, "DWG_ERR_CLASSESNOTFOUND"),
    (256, "DWG_ERR_SECTIONNOTFOUND"),
    (512, "DWG_ERR_PAGENOTFOUND"),
    (1024, "DWG_ERR_INTERNALERROR"),
    (2048, "DWG_ERR_INVALIDDWG"),
    (4096, "DWG_ERR_IOERROR"),
    (8192, "DWG_ERR_OUTOFMEM"),
)
_KNOWN_MASK = sum(bit for bit, _ in _ERROR_FLAGS)
_CRITICAL_MASK = sum(bit for bit, _ in _ERROR_FLAGS if bit >= 128)


def decode_libredwg_error_mask(mask: int) -> dict[str, Any]:
    """Explain observed *C-API* flags without inventing their source object.

    A mask of zero is only zero for the measured call; it is not evidence of
    class/geometry/revision/SHX completeness.
    """
    if type(mask) is not int or not 0 <= mask <= (2**31 - 1):
        raise ValueError("LibreDWG C-API bitmask must be a bounded nonnegative int")
    matched = [{"bit": bit, "name": name} for bit, name in _ERROR_FLAGS if mask & bit]
    unknown_bits = mask & ~_KNOWN_MASK
    status = (
        "UNKNOWN_C_API_ERROR_BITS_NO_GO" if unknown_bits
        else "DECODE_ERROR_FLAGS_PRESENT_NO_GO" if mask
        else "ZERO_MASK_ONLY_NOT_FULL_SOURCE_VALIDATION"
    )
    return {
        "policy": "structuralpro_p8p2_libredwg_c_api_mask_v1",
        "observed_c_api_mask": mask,
        "flags": matched,
        "known_mask": mask & _KNOWN_MASK,
        "unknown_bits": unknown_bits,
        "contains_critical_bits": bool(mask & _CRITICAL_MASK or unknown_bits),
        "status": status,
        "unhandled_class_causation_verified": False,
        "out_of_bounds_causation_verified": False,
        "map_aec_causation_verified": False,
        "opaque_payload_semantics_verified": False,
        "engineering_source_integrity_approved": False,
        "financial_quantity_approved": False,
    }


def libredwg_cli_receipt(cli_exit_code: int, *, converter_is_libredwg: bool) -> dict[str, Any]:
    """Report a real CLI observation, NEVER relabel it as C-API success.

    There is no trusted C-API observation in this pathway. A separate,
    source-bound native adapter is needed before the bitmask can be verified.
    """
    if type(cli_exit_code) is not int or not -1 <= cli_exit_code <= 65535:
        raise ValueError("Invalid converter CLI exit status")
    if type(converter_is_libredwg) is not bool:
        raise ValueError("converter_is_libredwg must be boolean")
    return {
        "policy": "structuralpro_p8p2_libredwg_cli_evidence_v1",
        "cli_exit_code": cli_exit_code,
        "libredwg_binary_claimed": converter_is_libredwg,
        "c_api_error_mask": None,
        "c_api_error_mask_verified": False,
        "c_api_status": (
            "NOT_OBSERVED_C_API_BITMASK_CLI_ONLY" if converter_is_libredwg
            else "NOT_APPLICABLE_NOT_LIBREDWG_CLI"
        ),
        "cli_success_is_lossless_conversion_proof": False,
        "financial_quantity_approved": False,
    }