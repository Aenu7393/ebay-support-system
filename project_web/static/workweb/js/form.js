async function loadCategoryFields() {
    const categoryID = document.getElementById('category').value;

    try {
        // APIからカテゴリ情報を取得
        const response = await fetch(`/api/get-category-fields/?category_id=${categoryID}`);
        if (!response.ok) throw new Error("カテゴリ情報の取得に失敗しました");

        const fields = await response.json();
        const dynamicFields = document.getElementById('dynamicFields');
        dynamicFields.innerHTML = ''; // 既存のフィールドをクリア

        // 必須項目を生成
        fields.forEach(field => {
            const label = document.createElement('label');
            label.textContent = field.name;

            const input = document.createElement('input');
            input.name = field.name;
            input.required = field.required;
            input.placeholder = `${field.name}を入力`;

            dynamicFields.appendChild(label);
            dynamicFields.appendChild(input);
        });
    } catch (error) {
        alert("カテゴリ情報の取得中にエラーが発生しました");
        console.error(error);
    }
}