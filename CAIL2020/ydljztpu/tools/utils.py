
import collections
from transformers import  BasicTokenizer, BertTokenizer
import logging


def get_final_text(pred_text, orig_text, do_lower_case, verbose_logging=False):
    """Project the tokenized prediction back to the original text."""

    # When we created the data, we kept track of the alignment between original
    # (whitespace tokenized) tokens and our WordPiece tokenized tokens. So
    # now `orig_text` contains the span of our original text corresponding to the
    # span that we predicted.
    #
    # However, `orig_text` may contain extra characters that we don't want in
    # our prediction.
    #
    # For example, let's say:
    #   pred_text = steve smith
    #   orig_text = Steve Smith's
    #
    # We don't want to return `orig_text` because it contains the extra "'s".
    #
    # We don't want to return `pred_text` because it's already been normalized
    # (the SQuAD eval script also does punctuation stripping/lower casing but
    # our tokenizer does additional normalization like stripping accent
    # characters).
    #
    # What we really want to return is "Steve Smith".
    #
    # Therefore, we have to apply a semi-complicated alignment heruistic between
    # `pred_text` and `orig_text` to get a character-to-charcter alignment. This
    # can fail in certain cases in which case we just return `orig_text`.

    def _strip_spaces(text):
        ns_chars = []
        ns_to_s_map = collections.OrderedDict()
        for (i, c) in enumerate(text):
            if c == " ":
                continue
            ns_to_s_map[len(ns_chars)] = i
            ns_chars.append(c)
        ns_text = "".join(ns_chars)
        # ns_text: 原始文本去掉所有空格 ns_to_s_map：原始文本中字符的位置与ns_text中字符的映射关系
        return (ns_text, ns_to_s_map)

    # We first tokenize `orig_text`, strip whitespace from the result
    # and `pred_text`, and check if they are the same length. If they are
    # NOT the same length, the heuristic has failed. If they are the same
    # length, we assume the characters are one-to-one aligned.
    # 基本的分词器，会分开空格和标点
    tokenizer = BasicTokenizer(do_lower_case=do_lower_case)

    tok_text = " ".join(tokenizer.tokenize(orig_text))

    # 在原始答案中寻找预测答案
    start_position = tok_text.find(pred_text)
    if start_position == -1:   # 如果找不到直接返回原始答案
        if verbose_logging:
            print("Unable to find text: '%s' in '%s'" % (pred_text, orig_text))
        return orig_text
    end_position = start_position + len(pred_text) - 1
    (orig_ns_text, orig_ns_to_s_map) = _strip_spaces(orig_text)
    (tok_ns_text, tok_ns_to_s_map) = _strip_spaces(tok_text)

    if len(orig_ns_text) != len(tok_ns_text):   # 如果原始答案与原始答案分词再组合后的去空格长度不相等，直接返回原始答案
        if verbose_logging:
            logging.info("Length not equal after stripping spaces: '%s' vs '%s'",
                        orig_ns_text, tok_ns_text)
        return orig_text

    # We then project the characters in `pred_text` back to `orig_text` using
    # the character-to-character alignment.
    tok_s_to_ns_map = {}
    for (i, tok_index) in tok_ns_to_s_map.items():
        tok_s_to_ns_map[tok_index] = i

    orig_start_position = None
    if start_position in tok_s_to_ns_map:
        ns_start_position = tok_s_to_ns_map[start_position]
        if ns_start_position in orig_ns_to_s_map:
            orig_start_position = orig_ns_to_s_map[ns_start_position]

    if orig_start_position is None:
        if verbose_logging:
            print("Couldn't map start position")
        return orig_text

    orig_end_position = None
    if end_position in tok_s_to_ns_map:
        ns_end_position = tok_s_to_ns_map[end_position]
        if ns_end_position in orig_ns_to_s_map:
            orig_end_position = orig_ns_to_s_map[ns_end_position]

    if orig_end_position is None:
        if verbose_logging:
            print("Couldn't map end position")
        return orig_text

    output_text = orig_text[orig_start_position:(orig_end_position + 1)]
    return output_text


def convert_to_tokens(features, ids, y1, y2, q_type):
    answer_dict = dict()
    # 一次迭代一个batch的数据
    for i, qid in enumerate(ids):   # article id
        answer_text = ''
        if q_type[i] == 0:
            doc_tokens = features[i][0]
            tok_tokens = doc_tokens[y1[i]: y2[i] + 1]
            tok_to_orig_map = features[i][6]
            if y2[i] < len(tok_to_orig_map):   # end位置合法
                orig_doc_start = tok_to_orig_map[y1[i]]
                orig_doc_end = tok_to_orig_map[y2[i]]
                orig_tokens = doc_tokens[orig_doc_start:(orig_doc_end + 1)]  # 这个才是对应的原文中的答案吧
                tok_text = " ".join(tok_tokens)

                # De-tokenize WordPieces that have been split off.
                tok_text = tok_text.replace(" ##", "")
                tok_text = tok_text.replace("##", "")

                # Clean whitespace
                tok_text = tok_text.strip()
                tok_text = " ".join(tok_text.split())  # 这句没啥意义
                orig_text = " ".join(orig_tokens).strip('[,.;]')    # 去除orig答案首尾的标点，不必要

                # 这个修正答案的，懒得看了
                final_text = get_final_text(tok_text, orig_text, do_lower_case=False, verbose_logging=False)
                answer_text = final_text
        elif q_type[i] == 1:
            answer_text = 'yes'
        elif q_type[i] == 2:
            answer_text = 'no'
        elif q_type[i] == 3:
            answer_text = 'unknown'
        answer_dict[qid.item()] = answer_text
    return answer_dict

