// خطاهای ثبت نام
async function validateRegister(){
    const nam = document.getElementById("fullname");
    const car = document.getElementById("username");
    const Emai = document.getElementById("email");
    const pas = document.getElementById("pass1");
    const Tek = document.getElementById("pass2");
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if(!nam || !car || !Emai || !pas || !Tek) return;

    if(nam.value === "") document.getElementById('fullname-error').style.display = 'block';
    if(car.value === "") document.getElementById('username-error').style.display = 'block';
    if(Emai.value === ""){
        document.getElementById('email-empty-error').style.display = 'block';
    } else if(!emailRegex.test(Emai.value)) {
        document.getElementById('For-empty-error').style.display = 'block';
    }
    if(pas.value === "") document.getElementById('pass1-empty-error').style.display = 'block';
    if(Tek.value === ""){
        document.getElementById('pass2-empty-error').style.display = 'block';
    } else if(Tek.value !== pas.value){
        document.getElementById('Tek-empty-error').style.display = 'block';
    }

    let isValid = true;
    if(pas.value.length < 8) isValid = false;
    if(!/[A-Z]/.test(pas.value)) isValid = false;
    if(!/[a-z]/.test(pas.value)) isValid = false;
    if(!/[0-9]/.test(pas.value)) isValid = false;
    if(!/[!@#$%^&*\-_]/.test(pas.value)) isValid = false;

    if(!isValid) {
        document.getElementById('pass1-empty-errora').style.display = 'block';
    } else {
       const { data, error } = await window.db.auth.signUp({
        email: Emai.value,
        password: pas.value
        });

        console.log(data);
        console.log(error);

        if(error){
        alert(error.message);
        return;
        }       
        window.location.href = "login.html";    
    }
}