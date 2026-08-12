"""
extract_cli.py — PDF 추출+DB저장 배치 루프 CLI (세션 비의존)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Streamlit 세션 밖에서 PDF 추출 배치를 실행한다.
브라우저 새로고침·세션 만료로 인한 중단 위험을 제거하고,
여러 파일을 연속 처리할 때 keep_alive 로 모델을 상주시켜 재로딩을 없앤다.

【추출 로직】 safety_core.extract_from_pdf 를 그대로 사용 — 결과 정확도 불변.

【사용법】
  # 단일 파일
  python extract_cli.py report.pdf

  # 여러 파일 / 폴더 전체
  python extract_cli.py reports/*.pdf
  python extract_cli.py --dir reports/

  # 모델 지정 (기본 qwen3:30b-a3b)
  python extract_cli.py --model qwen3:32b report.pdf

  # DB 저장 없이 추출 결과만 확인
  python extract_cli.py --no-save report.pdf
"""
import os
import sys
import glob
import time
import argparse

from safety_core import (
    extract_from_pdf, insert_accident, calculate_risk,
    COLUMNS, DEFAULT_MODEL,
)


def _collect_files(paths, dir_path):
    """인자로 받은 경로·글롭·폴더를 PDF 파일 목록으로 전개한다."""
    files = []
    if dir_path:
        files.extend(sorted(glob.glob(os.path.join(dir_path, "*.pdf"))))
    for p in paths:
        expanded = sorted(glob.glob(p))
        files.extend(expanded if expanded else [p])
    # 중복 제거(순서 유지) + PDF 만
    seen, out = set(), []
    for f in files:
        if f in seen:
            continue
        seen.add(f)
        if f.lower().endswith(".pdf") and os.path.isfile(f):
            out.append(f)
        else:
            print(f"  ⚠ 건너뜀(존재하지 않거나 PDF 아님): {f}")
    return out


def _make_progress(fname):
    """CLI 콘솔용 progress_fn — stdout 한 줄 갱신."""
    def _upd(pct, msg):
        bar = "█" * int(pct * 20) + "·" * (20 - int(pct * 20))
        sys.stdout.write(f"\r  [{bar}] {pct*100:5.1f}%  {msg[:40]:<40}")
        sys.stdout.flush()
    return _upd


def main():
    parser = argparse.ArgumentParser(
        description="PDF 사고보고서 추출+DB저장 배치 CLI (Streamlit 세션 비의존)"
    )
    parser.add_argument("paths", nargs="*", help="PDF 파일 경로 또는 글롭 패턴")
    parser.add_argument("--dir", dest="dir_path", default=None,
                        help="폴더 내 모든 *.pdf 처리")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"LLM 모델명 (기본 {DEFAULT_MODEL})")
    parser.add_argument("--no-save", action="store_true",
                        help="DB 저장 없이 추출만 수행")
    args = parser.parse_args()

    files = _collect_files(args.paths, args.dir_path)
    if not files:
        parser.error("처리할 PDF 파일이 없습니다. 경로 또는 --dir 를 지정하세요.")

    print(f"■ 대상 {len(files)}개 파일 · 모델 {args.model} · "
          f"{'추출만' if args.no_save else 'DB 저장'}")
    print("─" * 60)

    col_names = [n for n, _ in COLUMNS]
    empty = ('', None, 'null', 'NULL', 'None')
    ok = fail = 0
    batch_t0 = time.time()

    for idx, path in enumerate(files, 1):
        name = os.path.basename(path)
        print(f"[{idx}/{len(files)}] {name}")
        t0 = time.time()
        try:
            with open(path, "rb") as fp:
                pdf_bytes = fp.read()
            extracted, _ = extract_from_pdf(pdf_bytes, args.model, _make_progress(name))
            filled = sum(1 for k in col_names if extracted.get(k) not in empty)
            score, grade = calculate_risk(extracted)

            if args.no_save:
                row_id = "-"
            else:
                row_id = insert_accident(extracted, name)

            elapsed = time.time() - t0
            print(f"\r  ✅ ID {row_id} · {grade}({score}점) · "
                  f"필드 {filled}/{len(col_names)} · {elapsed:.1f}s"
                  + " " * 20)
            ok += 1
        except Exception as e:
            print(f"\r  ❌ 실패: {e}" + " " * 40)
            fail += 1

    total = time.time() - batch_t0
    print("─" * 60)
    print(f"■ 완료 · 성공 {ok} / 실패 {fail} · 총 {total:.1f}s "
          f"(평균 {total/max(len(files),1):.1f}s/파일)")


if __name__ == "__main__":
    main()
