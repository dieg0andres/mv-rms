if [ -n "${BASH_ENV:-}" ]; then
  RMS_TOOLCHAIN_DIR=$(CDPATH= cd -- "$(dirname -- "$BASH_ENV")" && pwd)
fi
: "${RMS_TOOLCHAIN_DIR:?Set RMS_TOOLCHAIN_DIR to the absolute RMS toolchain directory}"
case ":$PATH:" in
  *":$RMS_TOOLCHAIN_DIR/bin:"*) ;;
  *) PATH="$RMS_TOOLCHAIN_DIR/bin:$PATH" ;;
esac
export RMS_TOOLCHAIN_DIR PATH
export UV_PYTHON_INSTALL_DIR="$RMS_TOOLCHAIN_DIR/python"
export UV_CACHE_DIR="$RMS_TOOLCHAIN_DIR/cache"
