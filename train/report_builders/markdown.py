from .ppocr_result import pct, per_type_slice


def md_table(per_type, agg, title):
    lines = [f"**{title}**", "",
             "| тип | n | exact match | CER |", "|---|---|---|---|"]
    for t in sorted(per_type):
        v = per_type[t]
        lines.append(f"| `{t}` | {v['n']} | {pct(v['exact_match']):.2f} % | "
                     f"{pct(v['cer']):.2f} % |")
    lines.append(f"| **медиана по {agg['types']} типам** | {agg['items']} | "
                 f"**{pct(agg['exact_match_median']):.2f} %** | "
                 f"**{pct(agg['cer_median']):.2f} %** |")
    lines.append(f"| **micro по всем картинкам** | {agg['items']} | "
                 f"**{pct(agg['exact_match_micro']):.2f} %** | "
                 f"**{pct(agg['cer_micro']):.2f} %** |")
    return "\n".join(lines)


def print_tables(report, soup=None):
    zero_pt = report["zero_step"]["per_type"]
    zero_agg = report["zero_step"]["aggregate"]
    final_pt = report["after_training"]["per_type"]
    final_agg = report["after_training"]["aggregate"]

    print()
    print(md_table(zero_pt, zero_agg, "ZERO STEP (pretrained)"))
    print()
    print(md_table(final_pt, final_agg,
                    f"FINE-TUNED (best checkpoint, epoch {report['after_training']['best_epoch']})"))
    print()
    print("| эпоха | train loss | held-out median exact | median CER | micro exact | micro CER |")
    print("|---|---|---|---|---|---|")
    for h in report["after_training"]["all_evaluations"]:
        print(f"| {h['epoch']} | {h['loss']:.4f} | "
              f"{pct(h['exact_match_median']):.2f} % | {pct(h['cer_median']):.2f} % | "
              f"{pct(h['exact_match_micro']):.2f} % | {pct(h['cer_micro']):.2f} % |")
    if soup:
        print()
        print("| alpha | median exact | median CER | micro exact | micro CER |")
        print("|---|---|---|---|---|")
        for a, r in sorted(soup["results"].items(), key=lambda kv: float(kv[0])):
            g = r["aggregate"]
            print(f"| {a} | {pct(g['exact_match_median']):.2f} % | {pct(g['cer_median']):.2f} % | "
                  f"{pct(g['exact_match_micro']):.2f} % | {pct(g['cer_micro']):.2f} % |")
        best_a = max(soup["results"],
                     key=lambda a: (soup["results"][a]["aggregate"]["exact_match_median"] or 0))
        print()
        print(md_table(per_type_slice(soup["results"][best_a]["per_type"]),
                       soup["results"][best_a]["aggregate"],
                       f"INTERPOLATION alpha = {best_a} (best on the held-out median)"))
