import streamlit as st
import re
import os
import random

st.set_page_config(page_title="Мой тест", page_icon="📝", layout="wide")
st.title("📝 Тестирование")

def get_available_tests(base_dir):
    txt_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.txt'):
                rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                txt_files.append(rel_path)
    return sorted(txt_files)

@st.cache_data(show_spinner=False)
def parse_test(file_content):
    parts = re.split(r'Answer Key', file_content, flags=re.IGNORECASE)
    main_text = parts[0]
    key_text = parts[1] if len(parts) > 1 else ""

    answers = {}
    for line in key_text.strip().split('\n'):
        line = line.strip()
        if not line: continue
        
        match = re.match(r'^(\d+)\s*-\s*(.+)$', line)
        if match:
            q_num = int(match.group(1))
            ans_str = match.group(2).strip()
            
            letters = re.findall(r'\(([a-zа-я])\)', ans_str.lower())
            if letters:
                answers[q_num] = {'type': 'standard', 'val': letters}
            elif re.match(r'^\d+\s*-\s*[А-Яа-яA-Za-z]', ans_str):
                pairs = re.findall(r'(\d+)\s*-\s*([А-Яа-яA-Za-z])', ans_str)
                answers[q_num] = {'type': 'matching', 'val': dict(pairs)}
            else:
                nums = re.findall(r'\d', ans_str)
                answers[q_num] = {'type': 'sequence', 'val': nums, 'raw': ans_str}

    questions = {}
    current_q = None
    lines = main_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        q_match = re.match(r'^(\d+)\.\s+(.*)', line)
        if q_match:
            current_q = int(q_match.group(1))
            questions[current_q] = {'text': q_match.group(2), 'options': {}}
        elif current_q and line.startswith('('):
            opt_match = re.match(r'^\(([a-zа-я])\)\s*(.*)', line.lower())
            if opt_match:
                letter = opt_match.group(1)
                text = line[3:].strip()
                questions[current_q]['options'][letter] = text
            else:
                questions[current_q]['text'] += " " + line
        elif current_q:
            if re.match(r'^\d+\.', line):
                pass
            else:
                questions[current_q]['text'] += " " + line

    return questions, answers

base_dir = os.path.dirname(os.path.abspath(__file__))
available_files = get_available_tests(base_dir)

if not available_files:
    st.warning("В папке не найдено ни одного .txt файла с тестами!")
else:
    selected_file = st.selectbox("Выберите файл с тестами:", available_files)
    
    # Галочка для удаления дубликатов
    remove_dups = st.checkbox("Убрать повторяющиеся вопросы", value=True)

    if selected_file:
        file_path = os.path.join(base_dir, selected_file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            st.error(f"Ошибка при чтении файла: {e}")
            st.stop()

        questions, answers = parse_test(content)
        
        if not answers or not questions:
            st.warning("Не удалось найти вопросы или ключ ответов в этом файле.")
        else:
            # --- ПЕРЕМЕШИВАНИЕ И ОЧИСТКА ОТ ДУБЛИКАТОВ ---
            if ('shuffled_qs' not in st.session_state 
                or st.session_state.get('current_file') != selected_file 
                or st.session_state.get('remove_dups') != remove_dups):
                
                valid_qs = []
                seen_texts = set()
                
                for q_num in answers.keys():
                    if q_num in questions:
                        # Берем только те, где есть варианты или это спец-задания
                        if answers[q_num]['type'] == 'standard' and len(questions[q_num]['options']) > 0:
                            q_text = questions[q_num]['text'].strip().lower()
                            # Если нужно убрать дубликаты и такой текст уже был - пропускаем
                            if remove_dups and q_text in seen_texts:
                                continue
                            seen_texts.add(q_text)
                            valid_qs.append(q_num)
                        elif answers[q_num]['type'] == 'sequence' or (answers[q_num]['type'] == 'matching' and "Дон" in questions[q_num]['text']):
                            q_text = questions[q_num]['text'].strip().lower()
                            if remove_dups and q_text in seen_texts:
                                continue
                            seen_texts.add(q_text)
                            valid_qs.append(q_num)
                
                random.shuffle(valid_qs)
                st.session_state['shuffled_qs'] = valid_qs
                st.session_state['current_file'] = selected_file
                st.session_state['remove_dups'] = remove_dups
                
                shuffled_options = {}
                for q_num in valid_qs:
                    if answers[q_num]['type'] == 'standard':
                        opts = list(questions[q_num]['options'].keys())
                        random.shuffle(opts)
                        shuffled_options[q_num] = opts
                st.session_state['shuffled_options'] = shuffled_options
            
            current_qs = st.session_state['shuffled_qs']
            current_opts = st.session_state['shuffled_options']
            
            if not current_qs:
                st.info("Все вопросы оказались дубликатами или не найдены.")
            else:
                st.success(f"Загружено уникальных вопросов: {len(current_qs)}")
                
                with st.form("quiz_form"):
                    user_answers = {}
                    
                    for q_index, q_num in enumerate(current_qs):
                        q_data = questions[q_num]
                        ans_data = answers[q_num]
                        
                        st.markdown(f"**Вопрос {q_index + 1}.** {q_data['text']}")
                        
                        if ans_data['type'] == 'standard':
                            correct_opts = ans_data['val']
                            shuffled_letters = current_opts.get(q_num, [])
                            
                            if len(correct_opts) == 1:
                                options_list = [f"({k}) {q_data['options'][k]}" for k in shuffled_letters]
                                choice = st.radio("Выберите ответ:", options_list, key=f"q_{q_num}", index=None, label_visibility="collapsed")
                                if choice: user_answers[q_num] = [choice[1]]
                            else:
                                st.write("Выберите все правильные варианты:")
                                selected = []
                                for k in shuffled_letters:
                                    if st.checkbox(f"({k}) {q_data['options'][k]}", key=f"q_{q_num}_{k}"):
                                        selected.append(k)
                                if selected: user_answers[q_num] = selected

                        elif ans_data['type'] == 'matching':
                            if "Дон" in q_data['text']:
                                st.info(f"👉 **Сложное задание (запомните):** {ans_data['raw']}")
                            else:
                                for i in range(1, 10):
                                    col1, col2 = st.columns([1, 4])
                                    with col1:
                                        st.write(f"Вопрос {i}")
                                    with col2:
                                        options = ["Не выбрано"] + list(q_data['options'].values())
                                        choice = st.selectbox(f"Ответ для {i}", options, key=f"q_{q_num}_{i}", label_visibility="collapsed")
                                        if choice != "Не выбрано":
                                            user_answers[q_num] = user_answers.get(q_num, {})
                                            user_answers[q_num][str(i)] = choice

                        elif ans_data['type'] == 'sequence':
                            st.write(f"💡 *Правильный порядок: {ans_data['raw']}*") 
                            seq_input = st.text_input("Введите последовательность (например: 1, 2, 3, 4):", key=f"q_{q_num}")
                            user_answers[q_num] = re.findall(r'\d', seq_input)

                        else:
                            st.info(f"Ответ: {ans_data.get('raw', '')}")
                            user_answers[q_num] = []
                        
                        st.divider()
                        
                    submitted = st.form_submit_button("Проверить результаты")

                if submitted:
                    score = 0
                    total_checked = 0
                    st.header("Результаты")
                    
                    for q_num in answers.keys():
                        if q_num not in current_qs: continue
                        ans_data = answers[q_num]
                        user_ans = user_answers.get(q_num, [])
                        
                        if ans_data['type'] == 'standard':
                            if not questions[q_num]['options']: continue
                            total_checked += 1
                            if sorted(user_ans) == sorted(ans_data['val']):
                                score += 1
                            else:
                                st.error(f"Вопрос: {questions[q_num]['text']} \n\nВаш ответ: {user_ans}, Правильный: {ans_data['val']}")
                                
                        elif ans_data['type'] == 'sequence':
                            total_checked += 1
                            if user_ans == ans_data['val']:
                                score += 1
                            else:
                                st.error(f"Вопрос: {questions[q_num]['text']} \n\nОшибка. Ваш порядок: {user_ans}, Правильный: {ans_data['val']}")
                            
                    st.metric(label="Ваш результат", value=f"{score} из {total_checked}")
