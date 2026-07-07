from scholar_agent.critic import critique_survey, critique_survey_structured
from scholar_agent.reader import generate_paper_card
from scholar_agent.writer import revise_survey


def _valid_paper_indexes(indexes: list, paper_count: int) -> list[int]:
    valid = []

    for index in indexes:
        try:
            paper_index = int(index)
        except (TypeError, ValueError):
            continue

        if 1 <= paper_index <= paper_count and paper_index not in valid:
            valid.append(paper_index)

    return valid


def run_critic_revision_loop(
    topic: str,
    ranked_papers: list[dict],
    paper_cards: list[dict],
    initial_survey: str,
    reading_mode: str = "fast",
    max_pdf_pages: int = 20,
    max_rounds: int = 2,
) -> dict:
    survey = initial_survey
    cards = list(paper_cards)
    rounds = []

    for round_number in range(1, max_rounds + 1):
        critic_feedback = critique_survey_structured(
            topic=topic,
            paper_cards=cards,
            survey=survey,
        )

        needs_revision = bool(critic_feedback.get("needs_revision"))
        needs_reader_revision = bool(critic_feedback.get("needs_reader_revision"))

        round_record = {
            "round": round_number,
            "critic_feedback": critic_feedback,
            "reader_revised_indexes": [],
            "writer_revised": False,
        }

        if not needs_revision:
            rounds.append(round_record)
            break

        if needs_reader_revision:
            indexes = _valid_paper_indexes(
                critic_feedback.get("reader_paper_indexes", []),
                paper_count=min(len(ranked_papers), len(cards)),
            )

            for paper_index in indexes:
                cards[paper_index - 1] = generate_paper_card(
                    ranked_papers[paper_index - 1],
                    paper_index=paper_index,
                    reading_mode=reading_mode,
                    max_pdf_pages=max_pdf_pages,
                )

            round_record["reader_revised_indexes"] = indexes

        survey = revise_survey(
            topic=topic,
            paper_cards=cards,
            survey=survey,
            critic_feedback=critic_feedback,
        )
        round_record["writer_revised"] = True
        rounds.append(round_record)

    final_critic_report = critique_survey(
        topic=topic,
        paper_cards=cards,
        survey=survey,
    )

    return {
        "survey": survey,
        "paper_cards": cards,
        "critic_report": final_critic_report,
        "rounds": rounds,
        "revision_count": sum(1 for item in rounds if item["writer_revised"]),
        "reader_revision_count": sum(
            len(item["reader_revised_indexes"]) for item in rounds
        ),
    }
