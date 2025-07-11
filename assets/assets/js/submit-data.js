const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
const phoneRegex = /^(\+84|84|0)(3[2-9]|5[689]|7[06-9]|8[1-689]|9[0-46-9])[0-9]{7}$/;

const validateEmail = (email) => emailRegex.test(email);
const validatePhone = (phone) => {
  const cleanPhone = phone.replace(/[\s\-\(\)\.]/g, "");
  return phoneRegex.test(cleanPhone);
};

const antiSpam = (() => {
  let isSubmitting = false;
  let lastSubmit = 0;

  return {
    check: (cooldown = 3000) => {
      if (isSubmitting) return false;
      if (Date.now() - lastSubmit < cooldown) return false;
      return true;
    },
    start: () => (isSubmitting = true),
    end: () => {
      isSubmitting = false;
      lastSubmit = Date.now();
    },
  };
})();

// Popup helper
function showPopup(message, type = "success") {
  const popup = document.createElement("div");
  popup.className = `popup ${type}`;
  popup.innerHTML = `
    <div class="popup-content">
      <span class="popup-close">&times;</span>
      <p>${message}</p>
    </div>
  `;

  if (!document.getElementById("popup-styles")) {
    const style = document.createElement("style");
    style.id = "popup-styles";
    style.textContent = `
      .popup {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.5); display: flex;
        justify-content: center; align-items: center; z-index: 9999;
        animation: fadeIn 0.3s ease;
      }
      .popup-content {
        background: white; padding: 20px 30px; border-radius: 8px;
        text-align: center; position: relative; max-width: 400px;
        animation: slideIn 0.3s ease;
      }
      .popup.success .popup-content { border-left: 4px solid #28a745; }
      .popup.error .popup-content { border-left: 4px solid #dc3545; }
      .popup-close {
        position: absolute; top: 5px; right: 15px; font-size: 24px;
        cursor: pointer; color: #aaa;
      }
      .popup-close:hover { color: #000; }
      @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
      @keyframes slideIn { from { transform: translateY(-50px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
      @keyframes fadeOut { from { opacity: 1; } to { opacity: 0; } }
    `;
    document.head.appendChild(style);
  }

  document.body.appendChild(popup);

  const closePopup = () => {
    popup.style.animation = "fadeOut 0.3s ease";
    setTimeout(() => popup.remove(), 300);
  };

  popup.querySelector(".popup-close").onclick = closePopup;
  popup.onclick = (e) => {
    if (e.target === popup) closePopup();
  };
  setTimeout(closePopup, 3000);
}

// Hàm submit chung cho cả 2 form
async function submitForm(form, formType) {
  const submitBtn = form.querySelector('button[type="submit"]');
  const dataForm = new FormData(form);
  
  // Disable button
  const originalText = submitBtn.textContent;
  submitBtn.disabled = true;
  submitBtn.textContent = "ĐANG GỬI...";

  try {
    const GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyOU9SZUH7JfxO-XZ-lC2tJrNZZDrP6w69oqg9NA5VaO8Xy7alQ_lGPMbkbElm-xAAI/exec";

    // Tạo form ẩn
    const hiddenForm = document.createElement("form");
    hiddenForm.style.display = "none";
    hiddenForm.method = "POST";
    hiddenForm.action = GOOGLE_SCRIPT_URL;

    // Thêm form type để phân biệt
    const typeInput = document.createElement("input");
    typeInput.type = "hidden";
    typeInput.name = "form_type";
    typeInput.value = formType;
    hiddenForm.appendChild(typeInput);

    // Thêm tất cả field từ form gốc
    for (let [key, value] of dataForm.entries()) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = key;
      input.value = value;
      hiddenForm.appendChild(input);
    }

    // Thêm metadata
    const metaFields = {
      traffic_source: window.location.href,
      user_platform: navigator.userAgent
    };
    
    Object.entries(metaFields).forEach(([key, value]) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = key;
      input.value = value;
      hiddenForm.appendChild(input);
    });

    document.body.appendChild(hiddenForm);

    // Submit trong iframe ẩn
    const iframe = document.createElement("iframe");
    iframe.style.display = "none";
    iframe.name = `iframe_${formType}`;
    document.body.appendChild(iframe);

    hiddenForm.target = iframe.name;
    hiddenForm.submit();

    // Cleanup
    setTimeout(() => {
      document.body.removeChild(hiddenForm);
      document.body.removeChild(iframe);
    }, 1000);

    // Delay giả lập
    await new Promise((resolve) => setTimeout(resolve, 2000));

    showPopup(`Gửi dữ liệu thành công! Bác sĩ sẽ liên hệ với bạn sớm.`, "success");
    form.reset();
    console.log(`✅ ${formType} form submitted successfully!`);

  } catch (error) {
    showPopup("Có lỗi xảy ra. Vui lòng thử lại!", "error");
    console.error(`❌ ${formType} submit error:`, error);
  } finally {
    antiSpam.end();
    submitBtn.disabled = false;
    submitBtn.textContent = originalText;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Form 1: contacts-form
  const contactsForm = document.querySelector("#contacts-form");
  if (contactsForm) {
    contactsForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      if (!antiSpam.check(3000)) {
        showPopup("Vui lòng đợi trước khi gửi lại!", "error");
        return;
      }
      antiSpam.start();

      const dataForm = new FormData(contactsForm);
      const fname = dataForm.get("fname");
      const phone = dataForm.get("phone");
      const email = dataForm.get("Email");

      // Validate
      if (!fname || fname.trim().length < 2) {
        showPopup("Vui lòng nhập họ tên", "error");
        antiSpam.end();
        return;
      }
      if (!phone || !validatePhone(phone)) {
        showPopup("Vui lòng nhập đúng định dạng số điện thoại", "error");
        antiSpam.end();
        return;
      }
      if (email && !validateEmail(email)) {
        showPopup("Email không đúng định dạng", "error");
        antiSpam.end();
        return;
      }

      await submitForm(contactsForm, "contacts");
    });
  }

  // Form 2: appoinment-form
  const appointmentForm = document.querySelector("#appoinment-form");
  if (appointmentForm) {
    appointmentForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      if (!antiSpam.check(3000)) {
        showPopup("Vui lòng đợi trước khi gửi lại!", "error");
        return;
      }
      antiSpam.start();

      const dataForm = new FormData(appointmentForm);
      const name = dataForm.get("name");
      const phone = dataForm.get("phone");
      const message = dataForm.get("message");

      // Validate
      if (!name || name.trim().length < 2) {
        showPopup("Vui lòng nhập họ tên", "error");
        antiSpam.end();
        return;
      }
      if (!phone || !validatePhone(phone)) {
        showPopup("Vui lòng nhập đúng định dạng số điện thoại", "error");
        antiSpam.end();
        return;
      }
      if (!message || message.trim().length < 5) {
        showPopup("Vui lòng mô tả vấn đề của bạn", "error");
        antiSpam.end();
        return;
      }

      await submitForm(appointmentForm, "appointment");
    });
  }

  console.log("✅ Both forms initialized");
});