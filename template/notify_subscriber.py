"""HTML email template generator for editorial subscriber newsletters."""

import re
from datetime import datetime


def _format_summary_bullet(item: dict) -> str:
    """Creates a concise 1-line bullet for the top Executive Summary card."""
    title = item.get("title", "Update").strip()
    short_title = title.split(":")[0].strip() if ":" in title else title
    if len(short_title) > 35:
        short_title = short_title[:35].rsplit(" ", 1)[0]

    content = item.get("content", "")
    description = item.get("description", "").strip()

    takeaway = description
    if "## Final Takeaway" in content:
        parts = content.split("## Final Takeaway", 1)
        extracted = parts[1].strip().split("\n\n")[0].strip()
        if extracted:
            takeaway = re.sub(r"^[#\s*\-]+", "", extracted)
    elif "## Developer Experience" in content:
        parts = content.split("## Developer Experience", 1)
        extracted = parts[1].strip().split("\n\n")[0].strip()
        if extracted:
            takeaway = re.sub(r"^[#\s*\-]+", "", extracted)

    # Clean takeaway and pick first sentence
    takeaway = re.sub(r"[*`\[\]]", "", takeaway).strip()
    first_sentence = takeaway.split(". ")[0].strip()
    if not first_sentence.endswith("."):
        first_sentence += "."

    return f"""
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 10px;">
        <tr>
            <td width="18" valign="top" style="font-size: 14px; color: #1a73e8; line-height: 1.5;">&bull;</td>
            <td style="font-size: 13.5px; line-height: 1.55; color: #3c4043;">
                <strong style="color: #202124; font-weight: 600;">{short_title}:</strong> {first_sentence}
            </td>
        </tr>
    </table>
    """


def _format_article_html(item: dict, is_last: bool = False) -> str:
    """Transforms article into a clean, Google-styled editorial briefing block with Impact callout."""
    title = item.get("title", "Technical Update")
    description = item.get("description", "").strip()
    content = item.get("content", "")
    post_id = item.get("id") or item.get("slug") or ""
    link = f"https://newspluk.com/#article-{post_id}" if post_id else "https://newspluk.com"

    # Extract dynamic takeaway if available from article content
    takeaway = description
    if "## Final Takeaway" in content:
        parts = content.split("## Final Takeaway", 1)
        extracted = parts[1].strip().split("\n\n")[0].strip()
        if extracted:
            takeaway = re.sub(r"^[#\s*\-]+", "", extracted)
    elif "## Developer Experience" in content:
        parts = content.split("## Developer Experience", 1)
        extracted = parts[1].strip().split("\n\n")[0].strip()
        if extracted:
            takeaway = re.sub(r"^[#\s*\-]+", "", extracted)

    clean_summary = description
    clean_summary = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", clean_summary)
    clean_summary = re.sub(r"\*(.*?)\*", r"<em>\1</em>", clean_summary)

    clean_takeaway = takeaway
    clean_takeaway = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", clean_takeaway)
    clean_takeaway = re.sub(r"\*(.*?)\*", r"<em>\1</em>", clean_takeaway)

    border_bottom = "border-bottom: 1px solid #e8eaed; padding-bottom: 30px; margin-bottom: 30px;" if not is_last else "margin-bottom: 0;"

    return f"""
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="{border_bottom}">
        <tr>
            <td>
                <h2 class="article-headline" style="margin: 0 0 10px 0; font-size: 19px; font-weight: 600; color: #202124; line-height: 1.35; letter-spacing: -0.2px;">
                    <a href="{link}" style="color: #202124; text-decoration: none;">{title}</a>
                </h2>
                <p style="margin: 0 0 14px 0; font-size: 14px; line-height: 1.65; color: #3c4043;">
                    {clean_summary}
                </p>
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8f9fa; border-left: 3px solid #1a73e8; border-radius: 0 6px 6px 0;">
                    <tr>
                        <td style="padding: 12px 16px; font-size: 13.5px; line-height: 1.55; color: #3c4043;">
                            <span style="color: #1a73e8; font-weight: 700; margin-right: 4px;">Impact:</span>
                            {clean_takeaway}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    """


def notify_subscriber_template(header_or_articles, news_content: str = "", user_email: str = "", summary_content: str = "") -> str:
    """Renders the exact clean Google/NewsPluk Executive Daily Briefing email."""
    current_date = datetime.now().strftime("%A, %B %d, %Y").upper()
    current_year = datetime.now().year

    if isinstance(header_or_articles, list):
        articles = header_or_articles
        header = f"Your Daily Brief - NewsPluk: {articles[0].get('title', 'Daily Briefing')[:50]}" if articles else "Your Daily Brief - NewsPluk"

        # Generate Executive Summary bullets
        bullets = [_format_summary_bullet(art) for art in articles]
        summary_content = "\n".join(bullets)

        # Generate article blocks with Impact callouts
        blocks = [_format_article_html(art, is_last=(i == len(articles) - 1)) for i, art in enumerate(articles)]
        news_content = "\n".join(blocks)
    else:
        header = str(header_or_articles)

    summary_section = ""
    if summary_content:
        summary_section = f"""
            <!-- TOP SUMMARY CARD (Soft Executive Digest) -->
            <tr>
                <td class="summary-cell" style="padding: 26px 40px 0 40px;">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
                        style="background-color: #f8f9fa; border: 1px solid #e8eaed; border-radius: 8px;">
                        <tr>
                            <td style="padding: 18px 20px;">
                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
                                    style="margin-bottom: 12px;">
                                    <tr>
                                        <td style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #1a73e8;">
                                            Executive Summary
                                        </td>
                                    </tr>
                                </table>
                                {summary_content}
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{header}</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td, p, h1, h2, h3, span {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important; }}
    </style>
    <![endif]-->
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #f8f9fa;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            color: #202124;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}

        @media only screen and (max-width: 620px) {{
            .email-wrapper {{
                padding: 12px 6px !important;
            }}

            .email-container {{
                width: 100% !important;
                max-width: 100% !important;
                border-radius: 6px !important;
            }}

            .header-cell {{
                padding: 26px 20px 20px 20px !important;
            }}

            .body-cell {{
                padding: 20px 20px !important;
            }}

            .footer-cell {{
                padding: 26px 20px !important;
            }}

            .summary-cell {{
                padding: 18px 20px 0 20px !important;
            }}

            .article-headline {{
                font-size: 18px !important;
                line-height: 24px !important;
            }}
        }}
    </style>
</head>

<body style="margin: 0; padding: 0; background-color: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #202124;">
    <center class="email-wrapper" style="width: 100%; background-color: #f8f9fa; padding: 36px 12px; box-sizing: border-box;">
        <table class="email-container" role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"
            style="max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #dadce0; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(60, 64, 67, 0.08);">

            <!-- HEADER -->
            <tr>
                <td class="header-cell" style="padding: 36px 40px 24px 40px; border-bottom: 1px solid #e8eaed; background-color: #ffffff;">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                        <tr>
                            <td align="left" style="font-size: 11px; font-weight: 600; color: #5f6368; letter-spacing: 0.5px; text-transform: uppercase;">
                                {current_date}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding-top: 10px;">
                                <h1 style="margin: 0; font-size: 24px; font-weight: 600; color: #202124; letter-spacing: -0.5px; line-height: 1.25;">
                                    Your Daily Brief - NewsPluk
                                </h1>
                                <p style="margin: 6px 0 0 0; font-size: 13.5px; color: #5f6368; line-height: 1.5; font-weight: 400;">
                                    The day's essential developments, curated and distilled for quick reading.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>

            {summary_section}

            <!-- STORIES / NEWS ARTICLES LIST -->
            <tr>
                <td class="body-cell" style="padding: 26px 40px 32px 40px;">
                    {news_content}
                </td>
            </tr>

            <!-- CENTERED CLEAN FOOTER -->
            <tr>
                <td class="footer-cell" align="center"
                    style="padding: 28px 40px 32px 40px; background-color: #ffffff; border-top: 1px solid #e8eaed; font-size: 12px; line-height: 1.7; color: #5f6368; text-align: center;">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                        <tr>
                            <td align="center"
                                style="font-size: 12px; color: #5f6368; line-height: 1.7; text-align: center;">
                                You are receiving this briefing as a verified subscriber.<br>
                                Contact Support: <a href="mailto:contact@newspluk.com" style="color: #1a73e8; text-decoration: none; font-weight: 500;">contact@newspluk.com</a>
                            </td>
                        </tr>
                        <tr>
                            <td align="center"
                                style="padding-top: 8px; font-size: 11px; color: #80868b; text-align: center;">
                                &copy; {current_year} LucidTrend Systems. All rights reserved.
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>

        </table>
    </center>
</body>

</html>"""