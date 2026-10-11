"""Render cleanup run data for terminal review and JSON sidecars."""

import argparse
import pathlib


#============================================
def build_report(
		input_path: pathlib.Path,
		output_path: pathlib.Path,
		metrics: dict[str, object],
		skipped: set[str],
		args: argparse.Namespace,
		sampled: bool,
		pass_names: tuple[str, ...]) -> dict[str, object]:
	"""Build the same compact data for JSON diffs and terminal review."""
	report: dict[str, object] = {
		"input": str(input_path), "output": str(output_path), "sampled": sampled,
		"measure_only": args.measure, "skipped_passes": sorted(skipped),
		"enabled_passes": [name for name in pass_names if name not in skipped],
		"debris_min_lines": args.debris_min_lines,
		"debris_caption_window": args.debris_caption_window,
		"metrics": metrics,
	}
	return report


#============================================
def print_report(report: dict[str, object]) -> None:
	"""Print a small human report; examples remain in the adjacent sidecar."""
	metrics = report["metrics"]
	print(f"Input: {report['input']}")
	print(f"Output: {report['output']}")
	print(f"Measure only: {'yes' if report['measure_only'] else 'no'}")
	print(f"Enabled passes: {', '.join(report['enabled_passes'])}")
	print(f"Lines/chars: {metrics['before_lines']}/{metrics['before_characters']} -> {metrics['after_lines']}/{metrics['after_characters']}")
	print(f"Source lines: {metrics['input_lines']} total; short-line ratio: {metrics['short_line_ratio']:.1%}")
	print(f"Tags: {', '.join(metrics['tag_names']) if metrics['tag_names'] else 'none'}")
	print(f"Figure debris: {metrics['figure_debris_candidates']} candidates, {metrics['figure_debris_removed_lines']} lines removed, {metrics['figure_debris_ambiguous_runs']} retained")
	print(f"Unresolved line-break hyphens: {metrics['unresolved_dehyphenation_candidates']} candidates")
	for example in metrics["unresolved_dehyphenation_examples"]:
		print(f"  Line {example['line']}: {example['prefix']}- / {example['continuation']}")
	print(f"Non-ASCII characters measured: {metrics['non_ascii_characters']}")
	for finding in metrics["symbol_findings"][:5]:
		print(f"Symbol {finding['codepoint']}: {finding['count']}")
	print(f"Audit events: {metrics.get('removal_events', 0)}")
	removal_counts = metrics["removal_counts"]
	if removal_counts:
		count_text = ", ".join(f"{name}={count}" for name, count in removal_counts.items())
		print(f"Audit counts: {count_text}")
		if metrics["tag_operations"]:
			print(f"Tag operations: {metrics['tag_operations']}")
		for pass_name, examples in metrics["removal_examples"].items():
			first_example = examples[0]
			print(f"Sample {pass_name} lines {first_example['line_start']}-{first_example['line_end']}: {first_example['preview']}")
