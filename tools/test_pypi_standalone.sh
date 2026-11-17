#!/usr/bin/env bash
# Verify core OmniPython PyPI distributions in isolated environments.
#
# Each package gets a fresh venv with only that wheel (+ pip-resolved deps from its
# manifest). Fails if import or a minimal smoke check errors.
#
# Usage:
#   ./tools/test_pypi_standalone.sh
#   ./tools/test_pypi_standalone.sh --desktop   # also SDL + pygame stacks
#
# See CONTRIBUTING.md

set -euo pipefail

BASE_VENV="${PYPI_STANDALONE_VENV:-/tmp/omnipython-pypi-standalone}"
DESKTOP=0

usage() {
    cat <<'EOF'
Usage: ./tools/test_pypi_standalone.sh [--desktop]

Install each PyPI package into its own venv and run a minimal import smoke test.

Options:
  --desktop  Also test SDLDisplay / PGDisplay stacks (headless SDL/pg)
  -h         This help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --desktop)
            DESKTOP=1
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

check_import() {
    local venv="$1"
    local py_code="$2"
    set +e
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy "$venv/bin/python" -c "$py_code"
    local ec=$?
    set -e
    # usdl2/SDL may deliver SIGRTMIN+15 during interpreter teardown after a successful run
    if [[ $ec -eq 0 || $ec -eq 177 ]]; then
        return 0
    fi
    exit "$ec"
}

test_package() {
    local pypi_name="$1"
    local py_code="$2"
    shift 2
    local extras=("$@")
    local venv="${BASE_VENV}-${pypi_name}"

    if [[ -z "$venv" || "$venv" == "/" || "$venv" == "$HOME" ]]; then
        echo "Refusing unsafe venv path: $venv" >&2
        exit 2
    fi
    rm -rf "$venv"
    python3 -m venv "$venv"
    "$venv/bin/pip" install -q -U pip
    # --pre: current releases are pre-releases.
    "$venv/bin/pip" install --pre "$pypi_name" "${extras[@]}"
    echo "--- $pypi_name ---"
    "$venv/bin/pip" freeze | sort
    check_import "$venv" "$py_code"
    echo "ok: $pypi_name"
    echo
}

# One distribution now carries the whole core lib/ tree, so this is a single
# install exercising every module it should have delivered -- rather than six
# installs of distributions that no longer exist separately.
test_package omnipython "
import events, keys, displaydev, audiodev, appdev, boarddev, multimer
print('events', events.KEYDOWN)
print('keys', keys.keyname(keys.K_UP))
print('multimer', multimer.Timer)
print('displaydev', displaydev.DisplayDriver.__name__)
print('audiodev', audiodev.AudioFormat.__name__)
print('boarddev', boarddev.bind_lazy.__name__)
r = appdev.App()
print('appdev', type(r).__name__)
r.stop_timers()
"

if [[ "$DESKTOP" -eq 1 ]]; then
    # omnipython-desktop supplies its usdl2 fallback; pygame-ce is an optional
    # runtime dependency of the explicit PGDisplay stack.
    # Distinct venv labels so the two stacks do not clobber each other.
    BASE_VENV="${BASE_VENV}-sdl" test_package omnipython-desktop "
from board_config import display_drv
print('sdldisplay', type(display_drv).__name__)
display_drv.fill(0)
display_drv.show()
if hasattr(display_drv, 'quit'):
    display_drv.quit()
"

    BASE_VENV="${BASE_VENV}-pg" test_package omnipython "
from displaydev.pgdisplay import PGDisplay
print('pgdisplay', PGDisplay.__name__)
" pygame-ce
fi

echo "All standalone PyPI smoke tests passed."
