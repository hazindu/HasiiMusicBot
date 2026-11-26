# ==============================================================================
# network.py - Shared yt-dlp network options
# ==============================================================================
# Every yt-dlp call merges these options so YouTube traffic goes through
# the configured proxy (e.g. Cloudflare WARP) and uses the bgutil PO token
# provider. Both are optional and controlled from .env:
#   YT_PROXY=socks5://warp:1080
#   POT_PROVIDER_URL=http://bgutil-provider:4416
# ==============================================================================

from HasiiMusic import config


def ytdlp_network_opts() -> dict:
    # Let yt-dlp fetch YouTube's JS challenge solver (run with deno) from
    # yt-dlp's GitHub if the installed yt-dlp-ejs package is missing/outdated.
    opts: dict = {"remote_components": ["ejs:github"]}
    if config.YT_PROXY:
        opts["proxy"] = config.YT_PROXY
    if config.POT_PROVIDER_URL:
        # Read by the bgutil-ytdlp-pot-provider plugin. Without this the
        # plugin still tries its default http://127.0.0.1:4416.
        opts["extractor_args"] = {
            "youtubepot-bgutilhttp": {"base_url": [config.POT_PROVIDER_URL]},
        }
    return opts
