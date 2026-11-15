from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from huggingface_hub import snapshot_download
import numpy as np
import pymupdf
from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
MODEL_FILES = (
    "1_Pooling/config.json",
    "config.json",
    "model.safetensors",
    "modules.json",
    "sentence_bert_config.json",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",
)
CHUNK_TOKENS = 300
OVERLAP_TOKENS = 50


@dataclass(frozen=True)
class Passage:
    document: str
    title: str
    page: int
    text: str


def page_text(page: pymupdf.Page) -> tuple[str, bool]:
    # Extraction order preserves the column flow encoded in the supplied PDFs.
    paragraphs = []
    for _, top, _, bottom, text, _, block_type in page.get_text("blocks"):
        if block_type != 0:
            continue
        if bottom < page.rect.height * 0.08 or top > page.rect.height * 0.94:
            continue
        text = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"(?<=\w)-\n(?=\w)", "-", text)
        text = "".join(char for char in text if char == "\n" or char.isprintable())
        paragraph = " ".join(text.split())
        if paragraph.casefold() == "references":
            return "\n\n".join(paragraphs), True
        if paragraph:
            paragraphs.append(paragraph)
    return "\n\n".join(paragraphs), False


def split_page(text: str, tokenizer):
    encoding = tokenizer(
        text,
        add_special_tokens=False,
        return_offsets_mapping=True,
        truncation=False,
        verbose=False,
    )
    offsets = encoding["offset_mapping"]
    starts = [start for start, _ in offsets]
    paragraph_ends = [bisect_right(starts, match.start()) for match in re.finditer(r"\n\n", text)]
    start = 0
    while start < len(offsets):
        end = min(start + CHUNK_TOKENS, len(offsets))
        if end < len(offsets):
            boundary = bisect_right(paragraph_ends, end)
            if boundary and paragraph_ends[boundary - 1] >= start + 250:
                end = paragraph_ends[boundary - 1]
        excerpt = " ".join(text[offsets[start][0] : offsets[end - 1][1]].split())
        if excerpt:
            yield excerpt
        if end == len(offsets):
            break
        start = end - OVERLAP_TOKENS


class PassageIndex:
    def __init__(self, directory: Path):
        documents = sorted(directory.glob("*.pdf"))
        if not documents:
            raise ValueError(f"No se encontraron PDFs en {directory}.")

        snapshot = snapshot_download(
            MODEL_NAME, revision=MODEL_REVISION, allow_patterns=MODEL_FILES
        )
        self.model = SentenceTransformer(snapshot, device="cpu", local_files_only=True)
        self.passages = []
        for path in documents:
            with pymupdf.open(path) as pdf:
                title = (pdf.metadata.get("title") or "").strip() or path.stem
                for page in pdf:
                    text, bibliography = page_text(page)
                    for excerpt in split_page(text, self.model.tokenizer):
                        self.passages.append(Passage(path.name, title, page.number + 1, excerpt))
                    if bibliography:
                        break
        if not self.passages:
            raise ValueError("Los PDFs no contienen texto extraíble.")

        self.vectors = self.model.encode(
            [f"passage: {passage.title}\n{passage.text}" for passage in self.passages],
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def search(self, question: str, limit: int = 6) -> list[Passage]:
        query = self.model.encode(f"query: {question}", normalize_embeddings=True)
        scores = self.vectors @ query
        ranking = np.argsort(-scores, kind="stable")[:limit]
        return [self.passages[index] for index in ranking]
