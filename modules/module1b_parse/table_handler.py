from shared import s3


def save_table_to_s3(table: dict, doi_slug: str, index: int) -> None:
    key = f"parsed/{doi_slug}/tables/table_{index}.md"
    content = f"# {table.get('caption', '')}\n\n{table.get('markdown', '')}"
    s3.upload(content.encode(), key=key, content_type="text/markdown")
