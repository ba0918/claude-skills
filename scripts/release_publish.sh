#!/bin/sh
# release workflow の公開フェーズ: タグ三分岐 → draft Release 完成 → atomic push → publish。
#
# 使い方: release_publish.sh <version(X.Y.Z)> <notes-file> <asset>...
# git / gh は PATH から解決する。テストは PATH に fake を置いて失敗経路を注入する
# （scripts/test_release_publish.py）。
#
# 公開順序が契約: 公開されるもの（tag / Release）は、非公開で完成できるもの
# （draft Release と asset）がすべて揃ってからでないと作らない。
# Git push と GitHub Release API を跨ぐ 2 相コミットは存在しないため失敗窓を
# ゼロにはできない。この順序は残る窓を「publish の API 1 呼び出し」だけに縮め、
# その窓で失敗しても再実行（draft 作り直し → publish）が冪等に回復する。
# タグ削除による補償はしない: fetch 済みの利用者から見えたタグを消すのは
# 付け替えと同種の害で、窓を縮める方が安全。
set -eu

VERSION="$1"
NOTES_FILE="$2"
shift 2

TAG="v$VERSION"
TARGET_SHA="$(git rev-parse HEAD)"

# --- 1) タグ三分岐: リモートが正。ローカルタグは判定に使わない ---
remote_tag="$(git ls-remote origin "refs/tags/$TAG")"
if [ -z "$remote_tag" ]; then
  if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
    local_sha="$(git rev-parse "$TAG^{commit}")"
    if [ "$local_sha" != "$TARGET_SHA" ]; then
      echo "local tag $TAG points to $local_sha, expected $TARGET_SHA" >&2
      exit 1
    fi
  else
    git tag -a "$TAG" -m "$TAG"
  fi
  tag_created=true
else
  remote_sha="$(git ls-remote origin "refs/tags/$TAG^{}" | cut -f1)"
  if [ -z "$remote_sha" ]; then
    echo "remote tag $TAG is not an annotated tag" >&2
    exit 1
  fi
  if [ "$remote_sha" != "$TARGET_SHA" ]; then
    echo "remote tag $TAG points to $remote_sha, expected $TARGET_SHA" >&2
    exit 1
  fi
  tag_created=false
fi

# --- 2) 既存 Release の三分岐 ---
# published 済み → 前回 run が publish まで完走している（publish は atomic push の後
# にしか走らないので、main / tag / asset も揃っている）。何もせず成功。
# draft 残骸 → 前回 run が publish 前に落ちた痕跡。draft は非公開でタグも持たない
# ため、安全に捨てて作り直す（asset 欠損の draft を部分修復するより単純で確実）。
if is_draft="$(gh release view "$TAG" --json isDraft -q .isDraft 2>/dev/null)"; then
  if [ "$is_draft" = "false" ]; then
    echo "release $TAG already published; nothing to do"
    exit 0
  fi
  gh release delete "$TAG" --yes
fi

# --- 3) draft Release を asset 込みで完成させる（失敗しても公開物ゼロ） ---
# --target は渡さない: changed=true の初回経路では release commit（HEAD）が
# まだ push されておらず、リモートで解決できない commitish を draft 作成時に
# 参照すると失敗する。publish（5）はタグの atomic push 後にしか走らず、タグが
# 既に存在する Release では target_commitish は未使用（GitHub 仕様）のため、
# 束縛は常に既存タグ = TARGET_SHA 経由で決まる。
gh release create "$TAG" \
  --draft \
  --title "$TAG" \
  --notes-file "$NOTES_FILE" \
  "$@"

# --- 4) commit と tag を 1 回の atomic push で公開 ---
if [ "$tag_created" = "true" ]; then
  git push --atomic origin HEAD:main "refs/tags/$TAG"
else
  git push --atomic origin HEAD:main
fi

# --- 5) publish（残る唯一の失敗窓。落ちても再実行が 2) の draft 再作成から回復する） ---
gh release edit "$TAG" --draft=false
