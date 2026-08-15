import os
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
    "Referer": "https://www.deyeinverter.com/",
}


def fetch_pdf(url: str, save_dir: str = "data/raw") -> str:
    """
    Downloads a PDF from a URL and saves it locally.
    Returns the local file path.
    """
    os.makedirs(save_dir, exist_ok=True)

    filename = url.split("/")[-1]
    filepath = os.path.join(save_dir, filename)

    if os.path.exists(filepath):
        print(f"[fetch] Already downloaded: {filepath}")
        return filepath

    print(f"[fetch] Downloading from {url} ...")
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    with open(filepath, "wb") as f:
        f.write(response.content)

    print(f"[fetch] Saved to {filepath}")
    return filepath


if __name__ == "__main__":
    DATASHEET_URL = "https://www.deyeinverter.com/deyeinverter/2023/10/07/datasheet_sun-4-12k-g06p3-eu-am2-p1_231007_en.pdf"
    path = fetch_pdf(DATASHEET_URL)
    print("Done. File at:", path)