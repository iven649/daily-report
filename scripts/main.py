from fetch_news import main as fetch_news
from fetch_products import main as fetch_products
from detect_festivals import main as detect_festivals
from process_content import main as process_content
from build_pages import main as build_pages

def main():
    fetch_news()
    fetch_products()
    detect_festivals()
    process_content()
    build_pages()
    print("[DONE] Daily report generated.")

if __name__ == "__main__":
    main()
