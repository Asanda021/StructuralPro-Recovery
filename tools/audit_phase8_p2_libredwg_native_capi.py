"""Run the pinned private LibreDWG C API diagnostic without public CAD uploads."""
import argparse
from core.drawings.libredwg_native_trace_runner import diagnose_private_source


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('original_dwg')
    p.add_argument('private_config_json')
    p.add_argument('compiled_native_helper')
    p.add_argument('linked_libredwg_so')
    p.add_argument('private_output_directory')
    args = p.parse_args()
    try:
        report = diagnose_private_source(args.original_dwg, args.private_config_json,
                                         args.compiled_native_helper, args.linked_libredwg_so,
                                         args.private_output_directory)
    except Exception as exc:
        # No source path, hashes, handles or native stderr in terminal output.
        print('BLOCKED_NATIVE_C_API_DIAGNOSTIC:', type(exc).__name__)
        return 2
    print('NATIVE_C_API_EXECUTED_MASK:', report['exact_libredwg_return_mask'],
          'VERDICT:', report['verdict'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())