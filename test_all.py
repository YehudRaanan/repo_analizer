"""
Automated test runner for all collectors.
Runs each collector against 30 repos of its type, plus 30 classify tests.
Saves results to a structured log for analysis.

Usage: python test_all.py
"""

import sys
import os
import json
import time
import traceback
import re
import tiktoken
from datetime import datetime

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# -- Repo lists by type (30 each) --

LIBRARY_REPOS = [
    "https://github.com/lodash/lodash",
    "https://github.com/axios/axios",
    "https://github.com/expressjs/express",
    "https://github.com/moment/moment",
    "https://github.com/chalk/chalk",
    "https://github.com/sindresorhus/got",
    "https://github.com/validatorjs/validator.js",
    "https://github.com/date-fns/date-fns",
    "https://github.com/cheeriojs/cheerio",
    "https://github.com/micromatch/micromatch",
    "https://github.com/psf/requests",
    "https://github.com/pallets/flask",
    "https://github.com/pallets/click",
    "https://github.com/django/django",
    "https://github.com/numpy/numpy",
    "https://github.com/pandas-dev/pandas",
    "https://github.com/pytest-dev/pytest",
    "https://github.com/psf/black",
    "https://github.com/python-pillow/Pillow",
    "https://github.com/sqlalchemy/sqlalchemy",
    "https://github.com/serde-rs/serde",
    "https://github.com/tokio-rs/tokio",
    "https://github.com/rayon-rs/rayon",
    "https://github.com/gin-gonic/gin",
    "https://github.com/stretchr/testify",
    "https://github.com/go-yaml/yaml",
    "https://github.com/rails/rails",
    "https://github.com/jekyll/jekyll",
    "https://github.com/spring-projects/spring-boot",
    "https://github.com/google/guava",
]

WEB_APP_REPOS = [
    "https://github.com/calcom/cal.com",
    "https://github.com/vercel/next.js",
    "https://github.com/nuxt/nuxt",
    "https://github.com/remix-run/remix",
    "https://github.com/withastro/astro",
    "https://github.com/sveltejs/kit",
    "https://github.com/gatsbyjs/gatsby",
    "https://github.com/redwoodjs/redwood",
    "https://github.com/blitz-js/blitz",
    "https://github.com/trpc/trpc",
    "https://github.com/shadcn-ui/taxonomy",
    "https://github.com/steven-tey/dub",
    "https://github.com/supabase/supabase",
    "https://github.com/documenso/documenso",
    "https://github.com/formbricks/formbricks",
    "https://github.com/plasmicapp/plasmic",
    "https://github.com/twentyhq/twenty",
    "https://github.com/hoppscotch/hoppscotch",
    "https://github.com/makeplane/plane",
    "https://github.com/immich-app/immich",
    "https://github.com/mattreid1/baojs",
    "https://github.com/vuejs/create-vue",
    "https://github.com/streamlit/streamlit",
    "https://github.com/grafana/grafana",
    "https://github.com/discourse/discourse",
    "https://github.com/mastodon/mastodon",
    "https://github.com/chatwoot/chatwoot",
    "https://github.com/maybe-finance/maybe",
    "https://github.com/excalidraw/excalidraw",
    "https://github.com/novuhq/novu",
]

CLI_TOOL_REPOS = [
    "https://github.com/sharkdp/bat",
    "https://github.com/sharkdp/fd",
    "https://github.com/BurntSushi/ripgrep",
    "https://github.com/ogham/exa",
    "https://github.com/dandavison/delta",
    "https://github.com/ajeetdsouza/zoxide",
    "https://github.com/junegunn/fzf",
    "https://github.com/jesseduffield/lazygit",
    "https://github.com/cli/cli",
    "https://github.com/charmbracelet/glow",
    "https://github.com/httpie/cli",
    "https://github.com/yt-dlp/yt-dlp",
    "https://github.com/tmux/tmux",
    "https://github.com/kovidgoyal/kitty",
    "https://github.com/neovim/neovim",
    "https://github.com/wez/wezterm",
    "https://github.com/starship/starship",
    "https://github.com/nushell/nushell",
    "https://github.com/alacritty/alacritty",
    "https://github.com/lsd-rs/lsd",
    "https://github.com/astral-sh/ruff",
    "https://github.com/astral-sh/uv",
    "https://github.com/jqlang/jq",
    "https://github.com/stedolan/jq",
    "https://github.com/direnv/direnv",
    "https://github.com/casey/just",
    "https://github.com/volta-cli/volta",
    "https://github.com/bootandy/dust",
    "https://github.com/muesli/duf",
    "https://github.com/ClementTsang/bottom",
]

BACKEND_REPOS = [
    "https://github.com/tiangolo/fastapi",
    "https://github.com/encode/starlette",
    "https://github.com/encode/django-rest-framework",
    "https://github.com/graphql-python/graphene",
    "https://github.com/PostHog/posthog",
    "https://github.com/saleor/saleor",
    "https://github.com/ToolJet/ToolJet",
    "https://github.com/strapi/strapi",
    "https://github.com/directus/directus",
    "https://github.com/hasura/graphql-engine",
    "https://github.com/supabase/realtime",
    "https://github.com/Kong/kong",
    "https://github.com/traefik/traefik",
    "https://github.com/minio/minio",
    "https://github.com/go-gitea/gitea",
    "https://github.com/pocketbase/pocketbase",
    "https://github.com/nocodb/nocodb",
    "https://github.com/medusajs/medusa",
    "https://github.com/parse-community/parse-server",
    "https://github.com/nestjs/nest",
    "https://github.com/adonisjs/core",
    "https://github.com/vapor/vapor",
    "https://github.com/actix/actix-web",
    "https://github.com/gin-gonic/gin",
    "https://github.com/gofiber/fiber",
    "https://github.com/labstack/echo",
    "https://github.com/gorilla/mux",
    "https://github.com/spring-projects/spring-framework",
    "https://github.com/keycloak/keycloak",
    "https://github.com/supertokens/supertokens-core",
]

DATA_ML_REPOS = [
    "https://github.com/huggingface/transformers",
    "https://github.com/pytorch/pytorch",
    "https://github.com/tensorflow/tensorflow",
    "https://github.com/keras-team/keras",
    "https://github.com/scikit-learn/scikit-learn",
    "https://github.com/openai/whisper",
    "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
    "https://github.com/facebookresearch/detectron2",
    "https://github.com/ultralytics/ultralytics",
    "https://github.com/langchain-ai/langchain",
    "https://github.com/ggerganov/llama.cpp",
    "https://github.com/openai/CLIP",
    "https://github.com/Lightning-AI/pytorch-lightning",
    "https://github.com/huggingface/diffusers",
    "https://github.com/facebookresearch/fairseq",
    "https://github.com/microsoft/DeepSpeed",
    "https://github.com/ray-project/ray",
    "https://github.com/dmlc/xgboost",
    "https://github.com/mlflow/mlflow",
    "https://github.com/wandb/wandb",
    "https://github.com/apache/spark",
    "https://github.com/dbt-labs/dbt-core",
    "https://github.com/great-expectations/great_expectations",
    "https://github.com/iterative/dvc",
    "https://github.com/allegroai/clearml",
    "https://github.com/bentoml/BentoML",
    "https://github.com/onnx/onnx",
    "https://github.com/open-mmlab/mmdetection",
    "https://github.com/PaddlePaddle/PaddleOCR",
    "https://github.com/facebookresearch/segment-anything",
]

INFRA_REPOS = [
    "https://github.com/hashicorp/terraform-aws-consul",
    "https://github.com/hashicorp/terraform-aws-vault",
    "https://github.com/terraform-aws-modules/terraform-aws-vpc",
    "https://github.com/terraform-aws-modules/terraform-aws-eks",
    "https://github.com/terraform-aws-modules/terraform-aws-s3-bucket",
    "https://github.com/terraform-aws-modules/terraform-aws-lambda",
    "https://github.com/terraform-aws-modules/terraform-aws-rds",
    "https://github.com/gruntwork-io/terragrunt",
    "https://github.com/hashicorp/terraform",
    "https://github.com/pulumi/pulumi",
    "https://github.com/pulumi/examples",
    "https://github.com/crossplane/crossplane",
    "https://github.com/kubernetes/kubernetes",
    "https://github.com/helm/charts",
    "https://github.com/helm/helm",
    "https://github.com/argoproj/argo-cd",
    "https://github.com/ansible/ansible",
    "https://github.com/geerlingguy/ansible-role-docker",
    "https://github.com/geerlingguy/ansible-for-devops",
    "https://github.com/prometheus/prometheus",
    "https://github.com/grafana/loki",
    "https://github.com/istio/istio",
    "https://github.com/linkerd/linkerd2",
    "https://github.com/cert-manager/cert-manager",
    "https://github.com/external-secrets/external-secrets",
    "https://github.com/bitnami/charts",
    "https://github.com/docker/compose",
    "https://github.com/traefik/traefik-helm-chart",
    "https://github.com/cloudflare/terraform-provider-cloudflare",
    "https://github.com/flannel-io/flannel",
]

ALL_TYPES = {
    "library": LIBRARY_REPOS,
    "web_app": WEB_APP_REPOS,
    "cli_tool": CLI_TOOL_REPOS,
    "backend": BACKEND_REPOS,
    "data_ml": DATA_ML_REPOS,
    "infra": INFRA_REPOS,
}

# Mapping from ALL_TYPES keys to classify score type names
TYPE_TO_SCORE_NAME = {
    "library": "Library",
    "web_app": "Web App",
    "cli_tool": "CLI",
    "backend": "Backend",
    "data_ml": "Data/ML",
    "infra": "Infra",
}


def parse_url(url):
    """Extract owner and repo name from a GitHub URL."""
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not match:
        return None, url
    return match.group(1), match.group(2)


def count_tokens(text):
    """Count tokens using tiktoken (cl100k_base, used by most LLMs)."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def run_single_test(script_module, url, timeout_sec=60):
    """Run a single collector test and return result dict."""
    owner, repo_name = parse_url(url)

    result = {
        "url": url,
        "owner": owner,
        "repo": repo_name,
        "status": "unknown",
        "sections_found": [],
        "sections_empty": [],
        "error": None,
        "output_file": None,
        "file_chars": 0,
        "file_tokens": 0,
    }

    try:
        out_file = script_module.collect_and_save(url)
        result["output_file"] = out_file
        result["status"] = "success"

        # Analyze output file
        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()

        result["file_chars"] = len(content)
        result["file_tokens"] = count_tokens(content)

        # Check each section
        sections = re.findall(r"^--- (.+?) ---$", content, re.MULTILINE)
        for section in sections:
            # Check if section has content (not empty or just "none found")
            pattern = f"--- {re.escape(section)} ---\n(.+?)(?=\n--- |$)"
            sec_match = re.search(pattern, content, re.DOTALL)
            if sec_match:
                sec_content = sec_match.group(1).strip()
                if sec_content and "(No " not in sec_content and "(None " not in sec_content and "(none)" not in sec_content:
                    result["sections_found"].append(section)
                else:
                    result["sections_empty"].append(section)
            else:
                result["sections_empty"].append(section)

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def run_classify_test(url):
    """Run classify_collector and return result dict."""
    import classify_collector

    owner, repo_name = parse_url(url)

    result = {
        "url": url,
        "owner": owner,
        "repo": repo_name,
        "status": "unknown",
        "scores": {},
        "top_type": None,
        "signals": {},
        "error": None,
        "file_chars": 0,
        "file_tokens": 0,
    }

    try:
        out_file = classify_collector.collect_and_save(url)
        result["status"] = "success"
        result["output_file"] = out_file

        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()

        result["file_chars"] = len(content)
        result["file_tokens"] = count_tokens(content)

        # Parse classification scores from the new format
        score_section = re.search(
            r"CLASSIFICATION SCORES.*?---\n(.+?)(?=\n---)",
            content, re.DOTALL,
        )
        if score_section:
            for line in score_section.group(1).strip().split("\n"):
                line = line.strip()
                score_match = re.match(r"(\w[\w/ ]+?):\s+(\d+)\s+\((.+)\)", line)
                if score_match:
                    type_name = score_match.group(1).strip()
                    score_val = int(score_match.group(2))
                    details = score_match.group(3).strip()
                    result["scores"][type_name] = score_val
                    if details != "no signals":
                        result["signals"][type_name] = details

        # Determine top type (highest score)
        if result["scores"]:
            result["top_type"] = max(result["scores"], key=result["scores"].get)

        # Parse boolean patterns
        bool_section = re.search(r"BOOLEAN PATTERN CHECKS ---\n(.+?)$", content, re.DOTALL)
        if bool_section:
            for line in bool_section.group(1).strip().split("\n"):
                line = line.strip()
                if ": yes" in line:
                    key = line.replace(": yes", "").strip()
                    result["signals"][f"bool_{key}"] = True

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def test_collector(collector_name, module_name, repos, results_log):
    """Test a specific collector against its repo list."""
    print(f"\n{'='*60}")
    print(f"TESTING: {collector_name} ({len(repos)} repos)")
    print(f"{'='*60}")

    module = __import__(module_name)
    type_results = []

    for i, url in enumerate(repos):
        print(f"  [{i+1}/{len(repos)}] {url}...")
        result = run_single_test(module, url)
        type_results.append(result)
        status_icon = "OK" if result["status"] == "success" else "FAIL"
        empty_count = len(result["sections_empty"])
        tokens = result.get("file_tokens", 0)
        print(f"    {status_icon} - {len(result['sections_found'])} sections with data, {empty_count} empty, {tokens} tokens")
        if result["error"]:
            print(f"    ERROR: {result['error']}")

        # Rate limit awareness - small delay
        time.sleep(0.5)

    results_log[collector_name] = type_results
    return type_results


def test_classify(results_log):
    """Test classify_collector against all repo types."""
    print(f"\n{'='*60}")
    print(f"TESTING: classify_collector (30 repos, 5 per type)")
    print(f"{'='*60}")

    # Pick 5 from each type = 30 total
    test_repos = []
    for type_name, repos in ALL_TYPES.items():
        for url in repos[:5]:
            test_repos.append((type_name, url))

    classify_results = []
    correct = 0
    total = 0

    for i, (expected_type, url) in enumerate(test_repos):
        print(f"  [{i+1}/{len(test_repos)}] ({expected_type}) {url}...")
        result = run_classify_test(url)
        result["expected_type"] = expected_type
        classify_results.append(result)

        total += 1
        expected_score_name = TYPE_TO_SCORE_NAME.get(expected_type, expected_type)
        is_correct = result.get("top_type") == expected_score_name
        if is_correct:
            correct += 1

        status_icon = "OK" if result["status"] == "success" else "FAIL"
        match_icon = "MATCH" if is_correct else "MISS"
        top = result.get("top_type", "?")
        scores_brief = ", ".join(
            f"{k}:{v}" for k, v in sorted(
                result.get("scores", {}).items(),
                key=lambda x: -x[1],
            )[:3]
        )
        tokens = result.get("file_tokens", 0)
        print(f"    {status_icon} {match_icon} - predicted:{top} expected:{expected_score_name} | scores: {scores_brief} | {tokens} tokens")
        if result["error"]:
            print(f"    ERROR: {result['error']}")
        time.sleep(0.5)

    print(f"\n  Classification accuracy: {correct}/{total} ({100*correct/total:.0f}%)")

    # Per-type accuracy
    for type_name in ALL_TYPES:
        score_name = TYPE_TO_SCORE_NAME.get(type_name)
        type_results = [r for r in classify_results if r["expected_type"] == type_name]
        type_correct = sum(1 for r in type_results if r.get("top_type") == score_name)
        print(f"    {type_name}: {type_correct}/{len(type_results)}")

    results_log["classify"] = classify_results
    return classify_results


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    results_log = {}

    print(f"Test run started: {datetime.now().isoformat()}")
    print(f"GitHub token: {'set' if os.environ.get('GITHUB_TOKEN') else 'NOT SET'}")

    # Test classify (30 repos)
    test_classify(results_log)

    # Test each collector (30 repos each)
    collectors = [
        ("library_collector", "library_collector", LIBRARY_REPOS),
        ("web_app_collector", "web_app_collector", WEB_APP_REPOS),
        ("cli_tool_collector", "cli_tool_collector", CLI_TOOL_REPOS),
        ("backend_collector", "backend_collector", BACKEND_REPOS),
        ("data_ml_collector", "data_ml_collector", DATA_ML_REPOS),
        ("infra_collector", "infra_collector", INFRA_REPOS),
    ]

    for name, module_name, repos in collectors:
        test_collector(name, module_name, repos, results_log)

    # Save raw results
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results_log, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n\nAll tests complete. Results saved to test_results.json")
    print(f"Finished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
