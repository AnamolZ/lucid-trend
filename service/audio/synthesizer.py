"""High-fidelity server-side neural audio narration synthesizer using Edge TTS."""

import os
import re
import asyncio
import logging
from service.tursodb.client import TursoDBService

DEFAULT_VOICE = "en-US-ChristopherNeural"
FALLBACK_VOICE = "en-US-EricNeural"

def clean_markdown_for_speech(title: str, markdown_content: str) -> str:
    """Transforms raw Markdown dispatch text into natural spoken narration prose."""
    if not markdown_content:
        return title or ""

    text = markdown_content

    # 1. Remove image tags: ![alt](url)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # 2. Replace code blocks with descriptive speech pauses
    text = re.sub(r"```[\w]*\n.*?\n```", " Code snippet omitted for audio narration. ", text, flags=re.DOTALL)

    # 3. Simplify inline code: `code` -> code
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # 4. Simplify markdown links: [label](url) -> label
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # 5. Remove heading markers (e.g. # Title -> Title)
    text = re.sub(r"^\s*#{1,6}\s+", "", text, flags=re.MULTILINE)

    # 6. Remove blockquote markers, horizontal rules, and list bullets
    text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # 7. Remove emphasis markers (**bold**, *italic*, __bold__)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # 8. Normalize spacing and punctuation pauses
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text).strip()

    # Prepend title with editorial introduction
    intro = f"{title}. Published by NewsPluk Technical Editorial.\n\n"
    full_narrative = intro + text

    # Cap narrative length if exceptionally verbose (keeps audio crisp and under 10 minutes)
    words = full_narrative.split()
    if len(words) > 1600:
        full_narrative = " ".join(words[:1600]) + " ... Full dispatch text continues on NewsPluk."

    return full_narrative


async def synthesize_audio_async(
    post_id: str,
    title: str,
    content: str,
    output_dirs: list = None,
    voice: str = DEFAULT_VOICE
) -> str:
    """Asynchronously synthesizes an article's narrative into an .m4a audio file."""
    import edge_tts

    if not post_id:
        return ""

    if output_dirs is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dirs = [
            os.path.join(base_dir, "public", "audio"),
            os.path.join(os.path.dirname(base_dir), "news-pluk", "public", "audio"),
        ]

    for d in output_dirs:
        os.makedirs(d, exist_ok=True)

    narrative_text = clean_markdown_for_speech(title, content)
    filename = f"{post_id}.m4a"
    primary_path = os.path.join(output_dirs[0], filename)

    try:
        logging.info(f"[AudioSynthesizer] Synthesizing narration for '{post_id}' using {voice}...")
        comm = edge_tts.Communicate(narrative_text, voice)
        await comm.save(primary_path)

        # Mirror file to secondary destinations (e.g. news-pluk/public/audio)
        if os.path.exists(primary_path):
            file_bytes = None
            with open(primary_path, "rb") as f:
                file_bytes = f.read()

            for dest_dir in output_dirs[1:]:
                try:
                    dest_path = os.path.join(dest_dir, filename)
                    with open(dest_path, "wb") as f:
                        f.write(file_bytes)
                except Exception as mirror_err:
                    logging.warning(f"[AudioSynthesizer] Failed mirroring audio to {dest_dir}: {mirror_err}")

            # Optional: Upload to Cloudflare R2 Object Storage for zero-egress cloud hosting
            r2_url = ""
            try:
                from service.storage.r2_client import r2_service
                if r2_service.is_configured():
                    r2_url = r2_service.upload_bytes(file_bytes, f"audio/{filename}", content_type="audio/mp4")
            except Exception as r2_err:
                logging.warning(f"[AudioSynthesizer] R2 upload warning for '{post_id}': {r2_err}")

            audio_url = r2_url if r2_url else f"/audio/{filename}"
            logging.info(f"[AudioSynthesizer] Successfully synthesized {len(file_bytes)} bytes audio: {audio_url}")

            # Update Turso DB record
            try:
                turso = TursoDBService()
                turso.update_post_audio(post_id, audio_url)
            except Exception as db_err:
                logging.error(f"[AudioSynthesizer] Failed updating Turso audio_url for '{post_id}': {db_err}")

            return audio_url

    except Exception as e:
        logging.error(f"[AudioSynthesizer] Synthesis error for '{post_id}' with {voice}: {e}")
        if voice != FALLBACK_VOICE:
            logging.info(f"[AudioSynthesizer] Retrying synthesis with fallback voice: {FALLBACK_VOICE}")
            return await synthesize_audio_async(post_id, title, content, output_dirs, voice=FALLBACK_VOICE)

    return ""


def synthesize_audio(post_id: str, title: str, content: str) -> str:
    """Synchronous convenience wrapper for audio synthesis."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(synthesize_audio_async(post_id, title, content))
        else:
            return asyncio.run(synthesize_audio_async(post_id, title, content))
    except Exception as e:
        logging.error(f"[AudioSynthesizer] Synchronous wrapper error: {e}")
        return ""

generate_post_audio = synthesize_audio
