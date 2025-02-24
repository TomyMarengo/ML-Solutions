import pandas as pd
import os
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import string
import snowballstemmer
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)


def compute_metrics(confusion_matrix):
    metrics = {}
    for category, values in confusion_matrix.items():
        TP = values['TP']
        FP = values['FP']
        TN = values['TN']
        FN = values['FN']

        accuracy = (TP + TN) / (TP + FP + TN +
                                FN) if (TP + FP + TN + FN) > 0 else 0
        precision = TP / (TP + FP) if (TP + FP) > 0 else 0
        recall = TP / (TP + FN) if (TP + FN) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision +
                                               recall) if (precision + recall) > 0 else 0

        metrics[category] = {
            'Accuracy': accuracy,
            'Precision': precision,
            'Recall': recall,
            'F1-Score': f1_score
        }

    return metrics


def compute_confusion_matrix(y_true, y_pred, categories):
    cm = {category: {'TP': 0, 'FP': 0, 'TN': 0, 'FN': 0}
          for category in categories}

    for true, pred in zip(y_true, y_pred):
        for category in categories:
            if true == category and pred == category:
                cm[category]['TP'] += 1
            elif true != category and pred == category:
                cm[category]['FP'] += 1
            elif true == category and pred != category:
                cm[category]['FN'] += 1
            elif true != category and pred != category:
                cm[category]['TN'] += 1

    return cm


class Tokenizer:
    def __init__(self, filter, sanitizer):
        self.filter = filter
        self.sanitizer = sanitizer

    def apply(self, text):
        return [self.sanitizer(word) for word in text.split() if self.filter(word)]


class NaiveBayesClassifier:
    def __init__(self, tokenizer):
        self.vocab = set()
        self.tokenizer = tokenizer
        self.class_priors = {}
        self.word_counts = {}
        self.class_word_counts = {}

    def fit(self, X, y):
        for i in range(len(X)):
            label = y.iloc[i]

            words = self.tokenizer.apply(X.iloc[i])
            self.vocab.update(words)
            if label not in self.class_word_counts:
                self.class_word_counts[label] = {}
                self.class_word_counts[label]['__total__'] = 0
            self.class_word_counts[label]['__total__'] += len(words)

            for word in words:
                if word not in self.class_word_counts[label]:
                    self.class_word_counts[label][word] = 0
                self.class_word_counts[label][word] += 1

        total_documents = len(y)
        self.class_priors = {
            label: count['__total__'] / total_documents for label, count in self.class_word_counts.items()}

    def predict(self, X):
        predictions = []
        for text in X:
            posteriors = self._calculate_posteriors(text)
            predictions.append(max(posteriors, key=posteriors.get))
        return predictions

    def classify(self, X, y, umbral, category):
        TP = 0
        FP = 0
        FN = 0
        TN = 0
        for index in range(len(X)):
            posteriors = self._calculate_posteriors(X.iloc[index])
            cat_prob = posteriors[category]
            total_sum = sum(posteriors.values())
            if cat_prob/total_sum > umbral:
                if y.iloc[index] == category:
                    TP += 1
                else:
                    FP += 1
            else:
                if y.iloc[index] == category:
                    FN += 1
                else:
                    TN += 1
        return TP, FP, FN, TN

    def _tokenize(self, text):
        return text.lower().split()

    def _calculate_posteriors(self, text):

        words = self.tokenizer.apply(text)
        posteriors = {}

        for label in self.class_priors:
            prior = self.class_priors[label]
            likelihood = 1.0

            for word in words:
                word_count = self.class_word_counts[label].get(word, 0)
                total_words = self.class_word_counts[label]['__total__']
                likelihood *= (word_count + 1) / \
                    (total_words + len(self.vocab))

            posteriors[label] = prior * likelihood

        return posteriors


def read_input(path='data/Noticias_argentinas'):

    pkl_file = path + '.pkl'
    excel_file = path + '.xlsx'

    if os.path.exists(pkl_file):

        df = pd.read_pickle(pkl_file)
        print("Loaded DataFrame from pickle file.")
    else:

        df = pd.read_excel(excel_file)
        df.to_pickle(pkl_file)
        print("Loaded DataFrame from Excel file and saved it to pickle.")

    df = df.iloc[:, :4]

    return df


def no_category_filter(df):
    # df.loc[df["categoria"] == "Destacadas",
    #        "categoria"] = "Noticias destacadas"
    df = df[df["categoria"] != "Destacadas"]
    df = df[df["categoria"] != "Noticias destacadas"]
    with_cat = df[df["categoria"].notna()]
    df["categoria"] = df["categoria"].fillna("Sin categoría")

    return df, with_cat


def train_test_split(df, test_size=0.3, random_state=None, stratify_column='categoria'):
    if random_state:
        np.random.seed(random_state)

    train_set = pd.DataFrame(columns=df.columns)
    test_set = pd.DataFrame(columns=df.columns)

    for category in df[stratify_column].unique():
        category_subset = df[df[stratify_column] == category]
        category_subset = category_subset.sample(
            frac=1)
        split_idx = int(len(category_subset) * (1 - test_size))
        train_subset = category_subset[:split_idx]
        test_subset = category_subset[split_idx:]

        train_subset = train_subset.dropna(how='all', axis=0)
        test_subset = test_subset.dropna(how='all', axis=0)

        if not train_subset.empty:
            train_set = pd.concat([train_set, train_subset], ignore_index=True)
        if not test_subset.empty:
            test_set = pd.concat([test_set, test_subset], ignore_index=True)

    train_set = train_set.sample(frac=1).reset_index(drop=True)
    test_set = test_set.sample(frac=1).reset_index(drop=True)

    return train_set, test_set


def split_train_test(df):
    RANDOM_STATE = 42

    train_set, test_set = train_test_split(
        df, test_size=0.2, random_state=RANDOM_STATE, stratify_column='categoria')

    return train_set, test_set


def extract_categories(df):
    categories = df['categoria'].unique()

    return categories


def split_x_y(df):
    x = df['titular']
    y = df['categoria']
    return x, y


def values_matrix(y_test, y_pred, categories):

    confusion_matrix = compute_confusion_matrix(y_test, y_pred, categories)
    print("Confusion Matrix:")
    for category, values in confusion_matrix.items():
        print(f"{category}: {values}")

    metrics = compute_metrics(confusion_matrix)
    print("Evaluation Metrics:")
    for category, values in metrics.items():
        print(f"{category}: {values}")


def plot_confusion_matrix(title, true_positive, false_negative, false_positive, true_negative):

    confusion_matrix = np.array([[true_positive, false_negative],
                                 [false_positive, true_negative]])

    plt.figure(figsize=(8, 6))
    sns.heatmap(confusion_matrix, annot=True, fmt='d', cmap='Blues',
                xticklabels=['Predicted Positive', 'Predicted Negative'],
                yticklabels=['Actual Positive', 'Actual Negative'])

    plt.xlabel('Predicted Label')
    plt.ylabel('True Label')
    plt.title(title)
    plt.show()


def macroaverage_values_matrix(y_test, y_pred, categories):
    matrix_size = len(categories)
    confusion_matrix = np.zeros((matrix_size, matrix_size), dtype=int)
    category_to_index = {category: i for i, category in enumerate(categories)}

    for true_label, pred_label in zip(y_test, y_pred):
        true_index = category_to_index[true_label]
        pred_index = category_to_index[pred_label]
        confusion_matrix[true_index, pred_index] += 1

    precision_per_class = []
    recall_per_class = []
    f1_per_class = []
    sum_TP = 0
    sum_FP = 0
    sum_FN = 0
    sum_TN = 0

    for i, category in enumerate(categories):
        TP = confusion_matrix[i, i]
        FP = sum(confusion_matrix[:, i]) - TP
        FN = sum(confusion_matrix[i, :]) - TP
        TN = np.sum(confusion_matrix) - (TP + FP + FN)

        if TP + FP > 0:
            precision = TP / (TP + FP)
        else:
            precision = 0
        precision_per_class.append(precision)

        if TP + FN > 0:
            recall = TP / (TP + FN)
        else:
            recall = 0
        recall_per_class.append(recall)

        if precision + recall > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0
        f1_per_class.append(f1)

        sum_TP += TP
        sum_FP += FP
        sum_FN += FN
        sum_TN += TN

    macro_precision = np.mean(precision_per_class)
    macro_recall = np.mean(recall_per_class)
    macro_f1 = np.mean(f1_per_class)

    total_correct = np.trace(confusion_matrix)
    total_predictions = np.sum(confusion_matrix)
    accuracy = total_correct / total_predictions

    print(f"Precisión (Macro Average): {macro_precision:.5f}")
    print(f"Exactitud (Accuracy): {accuracy:.5f}")
    print(f"F1 Score (Macro Average): {macro_f1:.5f}")


def remove_short_words(word, n=3):
    return len(word) > n


def remove_non_alpha(word):
    return word.isalpha()


def complex_filter(word):
    return remove_short_words(word) and remove_non_alpha(word)


def to_lower(word):
    return word.lower()


def remove_punctuation(word):
    return word.translate(str.maketrans('', '', string.punctuation))


stemmer = snowballstemmer.stemmer('spanish')


def stemming_es(palabra):
    return stemmer.stemWord(palabra)


def complex_sanitize(word):
    return to_lower(remove_punctuation(word))


def identity(word):
    return word


def identity_filter(word):
    return True


def custom_sanitizer(word):
    return stemming_es(to_lower(remove_punctuation(word)))


def custom_filter(word):
    return True


def show_matrix(y_test, y_pred, categories):

    matrix_size = len(categories)
    confusion_matrix = np.zeros((matrix_size, matrix_size), dtype=int)

    category_to_index = {category: i for i, category in enumerate(categories)}

    for true_label, pred_label in zip(y_test, y_pred):
        true_index = category_to_index[true_label]
        pred_index = category_to_index[pred_label]
        confusion_matrix[true_index, pred_index] += 1

    confusion_matrix_percentage = confusion_matrix.astype(
        float) / confusion_matrix.sum(axis=1)[:, np.newaxis] * 100

    sns.heatmap(confusion_matrix_percentage, annot=True, fmt=".2f", cmap="Blues",
                xticklabels=categories, yticklabels=categories, vmax=100)

    plt.xlabel('Predicted', fontsize=14)
    plt.ylabel('True', fontsize=14)
    plt.title('Confusion Matrix as Percentages', fontsize=16)
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.show()

    matrix_size = len(categories)
    confusion_matrix = np.zeros((matrix_size, matrix_size), dtype=int)

    category_to_index = {category: i for i, category in enumerate(categories)}

    for true_label, pred_label in zip(y_test, y_pred):
        true_index = category_to_index[true_label]
        pred_index = category_to_index[pred_label]
        confusion_matrix[true_index, pred_index] += 1

    sns.heatmap(confusion_matrix, annot=True, fmt="d", cmap="Blues",
                xticklabels=categories, yticklabels=categories)

    plt.xlabel('Predicted', fontsize=14)
    plt.ylabel('True', fontsize=14)
    plt.title('Confusion Matrix', fontsize=16)
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.show()


def roc(x_test, y_test, categories, nb_classifier):
    thresholds = np.linspace(0.0, 1.0, 11)

    plt.figure(figsize=(8, 6))
    plt.plot([0, 1], [0, 1], linestyle='--', color='gray',
             label='clasificación aleatoria')

    for category in categories:
        TP_percentages = []
        FP_percentages = []

        for threshold in thresholds:
            TP, FP, FN, TN = nb_classifier.classify(
                x_test, y_test, threshold, category)
            TP_percentage = TP / (TP + FN)
            FP_percentage = FP / (FP + TN)

            TP_percentages.append(TP_percentage)
            FP_percentages.append(FP_percentage)

        plt.plot(FP_percentages, TP_percentages,
                 marker='o', linestyle='-', label=category)

    plt.xlabel('Tasa de Falsos Positivos')
    plt.ylabel('Tasa de Verdaderos Positivos')

    plt.title('Tasa de FP vs Tasa de TP para diferentes umbrales')
    plt.legend(title='Categoría', loc='best')
    plt.grid(False)
    plt.show()


def main():
    df = read_input()
    df_no_cat, df_categories = no_category_filter(df)
    train_set, test_set = split_train_test(df_categories)
    x_train, y_train = split_x_y(train_set)
    x_test, y_test = split_x_y(test_set)

    tokenizer = Tokenizer(complex_filter, complex_sanitize)
    nb_classifier = NaiveBayesClassifier(tokenizer)
    nb_classifier.fit(x_train, y_train)

    categories = extract_categories(train_set)
    y_pred = nb_classifier.predict(x_test)

    show_matrix(y_test, y_pred, categories)
    macroaverage_values_matrix(y_test, y_pred, categories)

    print("Realizando la curva ROC, puede tardar un tiempo...")
    # roc(x_test, y_test, categories, nb_classifier)

    d_aux = df_no_cat[df_no_cat["categoria"] == "Sin categoría"]
    x_no_cat, _ = split_x_y(d_aux)

    y_pred = nb_classifier.predict(x_no_cat)
    d_aux["categoria"] = y_pred
    print(d_aux.to_string())

    category_counts = d_aux['categoria'].value_counts(normalize=True) * 100
    print(category_counts)


def no_filters():
    df = read_input()
    df_no_cat, df_categories = no_category_filter(df)
    train_set, test_set = split_train_test(df_categories)
    x_train, y_train = split_x_y(train_set)
    x_test, y_test = split_x_y(test_set)
    print(len(x_train))
    print(len(x_test))

    tokenizer = Tokenizer(identity_filter, identity)
    nb_classifier = NaiveBayesClassifier(tokenizer)
    nb_classifier.fit(x_train, y_train)

    categories = extract_categories(train_set)

    d_aux = df_no_cat[df_no_cat["categoria"] == "Sin categoría"]
    x_no_cat, _ = split_x_y(d_aux)
    y_pred = nb_classifier.predict(x_test)
    show_matrix(y_test, y_pred, categories)
    macroaverage_values_matrix(y_test, y_pred, categories)
    # print("Realizando la curva ROC, puede tardar un tiempo...")
    # roc(x_test, y_test, categories, nb_classifier)

    y_pred = nb_classifier.predict(x_no_cat)
    d_aux["categoria"] = y_pred
    # print(d_aux)


if __name__ == '__main__':
    main()
