from pipeline import run_pipeline


if __name__ == "__main__":
    result = run_pipeline("config_onet29.yaml")
    print(f"Run complete: {result['run_id']}")
