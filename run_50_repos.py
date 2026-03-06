import sys
import os
import time
import json
import logging
import subprocess
from typing import List, Dict

# Setup logging to output to a file and console
log_file = "test_50_repos_run.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

REPOS_TO_TEST = [
    # 1. Web Apps / Front-ends
    "https://github.com/freeCodeCamp/freeCodeCamp",
    "https://github.com/excalidraw/excalidraw",
    "https://github.com/mattermost/focalboard",
    "https://github.com/twentyhq/twenty",
    "https://github.com/hoppscotch/hoppscotch",
    "https://github.com/nocodb/nocodb",
    "https://github.com/requarks/wiki",
    "https://github.com/Infisical/infisical",
    "https://github.com/teableio/teable",
    "https://github.com/appsmithorg/appsmith",

    # 2. Backends & APIs
    "https://github.com/directus/directus",
    "https://github.com/medusajs/medusa",
    "https://github.com/mastodon/mastodon",
    "https://github.com/ghost/ghost",
    "https://github.com/posthog/posthog",
    "https://github.com/plausible/analytics",
    "https://github.com/grafana/oncall",
    "https://github.com/getsentry/sentry",
    "https://github.com/outline/outline",
    "https://github.com/chatwoot/chatwoot",

    # 3. CLI Tools & Desktop
    "https://github.com/rust-lang/cargo",
    "https://github.com/nushell/nushell",
    "https://github.com/alacritty/alacritty",
    "https://github.com/jesseduffield/lazydocker",
    "https://github.com/lsd-rs/lsd",
    "https://github.com/peco/peco",
    "https://github.com/extrawurst/gitui",
    "https://github.com/cantino/mcfly",
    "https://github.com/ogham/exa",
    "https://github.com/johanneskoester/snakemake",

    # 4. Data / ML / AI
    "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
    "https://github.com/hwchase17/langchain",
    "https://github.com/lucidrains/imagen-pytorch",
    "https://github.com/mlflow/mlflow",
    "https://github.com/apache/superset",
    "https://github.com/dbt-labs/dbt-core",
    "https://github.com/streamlit/streamlit",
    "https://github.com/microsoft/autogen",
    "https://github.com/ggerganov/llama.cpp",
    "https://github.com/CompVis/stable-diffusion",

    # 5. Infra / DevOps / Languages
    "https://github.com/fluent/fluentd",
    "https://github.com/goharbor/harbor",
    "https://github.com/cilium/cilium",
    "https://github.com/etcd-io/etcd",
    "https://github.com/istio/istio",
    "https://github.com/traefik/traefik",
    "https://github.com/hashicorp/vault",
    "https://github.com/gitea/gitea",
    "https://github.com/drone/drone",
    "https://github.com/open-telemetry/opentelemetry-collector"
]

TIMEOUT_SECONDS = 300  # 5 minutes per repo maximum

def run_repo(url: str) -> Dict:
    """Runs the analyze_repo.py script via subprocess with a timeout."""
    start_time = time.time()
    
    cmd = [sys.executable, "analyze_repo.py", url]
    
    result = {
        "url": url,
        "success": False,
        "duration": 0.0,
        "stdout": "",
        "stderr": "",
        "error": None
    }
    
    try:
        # We capture output to analyze Tokens, Steps, etc.
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            encoding='utf-8',
            errors='replace'
        )
        
        result["duration"] = time.time() - start_time
        result["stdout"] = process.stdout
        result["stderr"] = process.stderr
        
        if process.returncode == 0:
            result["success"] = True
        else:
            result["error"] = f"Exit code {process.returncode}"
            
    except subprocess.TimeoutExpired as e:
        result["duration"] = time.time() - start_time
        result["error"] = f"Timed out after {TIMEOUT_SECONDS} seconds"
        # Recover output up to the point of termination (if any)
        if hasattr(e, 'stdout') and e.stdout:
            result["stdout"] = e.stdout.decode('utf-8', 'replace') if isinstance(e.stdout, bytes) else e.stdout
            
    except Exception as e:
        result["duration"] = time.time() - start_time
        result["error"] = str(e)

    return result

def estimate_tokens(stdout_text: str) -> int:
    """
    Very rough estimation of tokens used based on characters printed in ReAct steps + final answer.
    Because we can't trace the exact Nebius API response headers without modifying `react_agent.py`,
    we approximate: 1 token ~= 4 chars of output.
    """
    return len(stdout_text) // 4


def generate_report(results: List[Dict]):
    report_file = "50_repos_test_report.md"
    
    total_duration = sum(r["duration"] for r in results)
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    
    total_estimated_tokens = sum(estimate_tokens(r["stdout"]) for r in results)
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# Automated 50-Repo LLM Analysis Report\n\n")
        f.write("## 📊 Summary Statistics\n")
        f.write(f"- **Total Repositories Tested**: {len(results)}\n")
        f.write(f"- **Successful Analyses**: {successful}\n")
        f.write(f"- **Failed/Timed Out**: {failed}\n")
        f.write(f"- **Total Execution Time**: {total_duration/60:.2f} minutes\n")
        f.write(f"- **Average Time per Repo**: {total_duration/len(results):.2f} seconds\n")
        f.write(f"- **Estimated Output Tokens Generated**: ~{total_estimated_tokens:,}\n\n")
        
        f.write("## ⚠️ Failures & Issues\n")
        if failed == 0:
            f.write("No failures! All repos analyzed successfully.\n")
        else:
            for r in results:
                if not r["success"]:
                    f.write(f"- **{r['url']}**: {r['error']}\n")
        f.write("\n---\n\n")
        
        f.write("## 📝 Detailed Logs per Repository\n\n")
        
        for r in results:
            status_emoji = "✅" if r["success"] else "❌"
            f.write(f"### {status_emoji} {r['url']}\n")
            f.write(f"- **Time**: {r['duration']:.2f}s\n")
            f.write(f"- **Est. Tokens**: {estimate_tokens(r['stdout'])}\n")
            
            if r["error"]:
                f.write(f"- **Error**: {r['error']}\n")
            
            # Try to grab just the ReAct Steps and Final Answer to keep report readable
            lines = r["stdout"].splitlines()
            react_lines = [line.strip() for line in lines if "Step " in line or "Thought:" in line or "Result:" in line]
            
            f.write("\n**ReAct Steps Taken:**\n```\n")
            if react_lines:
                f.write("\n".join(react_lines))
            else:
                f.write("(No ReAct steps recorded or output garbled)")
            f.write("\n```\n")
            
            # Find the final JSON/Summary block pattern
            try:
                final_answer_start = r["stdout"].index("============================================================")
                final_answer = r["stdout"][final_answer_start:]
                f.write("\n**Final Output:**\n```\n")
                f.write(final_answer.strip())
                f.write("\n```\n")
            except ValueError:
                f.write("\n*(Could not extract final formatted output from stdout)*\n")
            
            f.write("\n---\n")

def main():
    logging.info(f"Starting automated run of {len(REPOS_TO_TEST)} repositories.")
    results = []
    
    for i, url in enumerate(REPOS_TO_TEST, 1):
        logging.info(f"[{i}/{len(REPOS_TO_TEST)}] Analyzing {url}...")
        res = run_repo(url)
        
        status = "SUCCESS" if res["success"] else f"FAILED ({res['error']})"
        logging.info(f"  -> {status} in {res['duration']:.2f}s")
        results.append(res)
    
    logging.info("Run complete. Writing comprehensive markdown report...")
    generate_report(results)
    logging.info("Report written to 50_repos_test_report.md")

if __name__ == "__main__":
    main()
