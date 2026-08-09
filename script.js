if(localStorage.getItem('theme') === 'light') {
    document.body.classList.add('light');
}

const canvas = document.getElementById("matrix");
let ctx = null;

if(canvas) {
    ctx = canvas.getContext("2d");
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const fontSize = 19;
    const cols = Math.floor(canvas.width / fontSize);
    const drops = Array(cols).fill(1);
    const chars = "アイウエオ01{}01101[]</>()∑∆Ωλ".split('');

    function draw(){
        const isLight = document.body.classList.contains('light');
        ctx.fillStyle = isLight ? 'rgba(255, 255, 255, 0.4)' : 'rgba(10, 0, 20, 0.09)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = isLight ? '#00aa44' : '#8c00ff';
        ctx.font = fontSize + 'px monospace';
        drops.forEach(function(y, i) {
            const char = chars[Math.floor(Math.random() * chars.length)];
            ctx.fillText(char, i * fontSize, y * fontSize);
            if(drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                drops[i] = 0;
            }
            drops[i]++;
        });
    }
    setInterval(draw, 80);
}
// اسکرول انیمیشن
const reveals = document.querySelectorAll('.reveal');
if(reveals.length > 0) {
    window.addEventListener('scroll', function() {
        reveals.forEach(function(el) {
            const top = el.getBoundingClientRect().top;
            if(top < window.innerHeight - 100) {
                el.classList.add('active');
            }
        });
    });
}

// نمایش پسورد
function togglePass(input){
    const inputs = document.getElementById(input);
    if(inputs) {
        inputs.type = inputs.type === "password" ? "text" : "password";
    }
}

async function erores(){
        console.log('erores called');
    const erorryE = document.getElementById("email");
    const erorryP = document.getElementById("pass1");
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if(!erorryE || !erorryP) return;

    document.getElementById('email-empty-error').style.display = 'none';
    document.getElementById('For-empty-error').style.display = 'none';
    document.getElementById('pass1-empty-error').style.display = 'none';

    let isValid = true;

    if(erorryE.value === ""){
        document.getElementById('email-empty-error').style.display = 'block';
        isValid = false;
    } 

    if(erorryP.value === ""){
        document.getElementById('pass1-empty-error').style.display = 'block';
        isValid = false;
    }

    if(!isValid) return;

    const { data, error } = await window.db.auth.signInWithPassword({
        email: erorryE.value,
        password: erorryP.value
    });

    console.log('data:', data);
console.log('error:', error);

    if(error){
        alert('ایمیل یا رمز عبور اشتباه است');
        return;
    }

    window.location.href = 'index.html';
}

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

// قوانین پسورد
const pas = document.getElementById("pass1");
if(pas) {
    pas.addEventListener('input', function(){
        document.getElementById('rule-length') && (pas.value.length >= 8 
            ? document.getElementById('rule-length').classList.add('valid')
            : document.getElementById('rule-length').classList.remove('valid'));
        document.getElementById('rule-upper') && (/[A-Z]/.test(pas.value)
            ? document.getElementById('rule-upper').classList.add('valid')
            : document.getElementById('rule-upper').classList.remove('valid'));
        document.getElementById('rule-lower') && (/[a-z]/.test(pas.value)
            ? document.getElementById('rule-lower').classList.add('valid')
            : document.getElementById('rule-lower').classList.remove('valid'));
        document.getElementById('rule-number') && (/[0-9]/.test(pas.value)
            ? document.getElementById('rule-number').classList.add('valid')
            : document.getElementById('rule-number').classList.remove('valid'));
        document.getElementById('rule-special') && (/[!@#$%^&*\-_]/.test(pas.value)
            ? document.getElementById('rule-special').classList.add('valid')
            : document.getElementById('rule-special').classList.remove('valid'));
    });
}

// drawer
function openDrawer() {
    const drawer = document.getElementById('drawer');
    const overlay = document.getElementById('overlay');
    if(drawer) drawer.classList.add('open');
    if(overlay) overlay.classList.add('open');
}

function closeDrawer() {
    const drawer = document.getElementById('drawer');
    const overlay = document.getElementById('overlay');
    if(drawer) drawer.classList.remove('open');
    if(overlay) overlay.classList.remove('open');
}

// فراموشی رمز عبور
function forgotPass() {
    const email = document.getElementById('forgot-email');
    if(!email) return;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    document.getElementById('forgot-email-error').style.display = 'none';
    document.getElementById('forgot-format-error').style.display = 'none';
    document.getElementById('forgot-success').style.display = 'none';

    if(email.value === '') {
        document.getElementById('forgot-email-error').style.display = 'block';
    } else if(!emailRegex.test(email.value)) {
        document.getElementById('forgot-format-error').style.display = 'block';
    } else {
        document.getElementById('forgot-success').style.display = 'block';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const modeBtn = document.querySelector('.mode');
    if(modeBtn) {
        modeBtn.addEventListener('click', function() {
            document.body.classList.toggle('light');
            if(document.body.classList.contains('light')) {
                localStorage.setItem('theme', 'light');
            } else {
                localStorage.setItem('theme', 'dark');
            }
            if(ctx) {
                ctx.fillStyle = document.body.classList.contains('light') ? 'white' : '#0a0020';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
            }
        });
    }
});

const courses = [
    { keywords: ['پایتون', 'python'], url: 'python.html' },
    { keywords: ['html', 'اچ تی ام ال'], url: 'html.html' },
    { keywords: ['css', 'سی اس اس'], url: 'css.html' },
    { keywords: ['javascript', 'جاوا اسکریپت', 'js'], url: 'js.html' },
    { keywords: ['php', 'پی اچ پی'], url: 'php.html' },
];

function doSearch() {
    const input = document.querySelector('.inp');
    if(!input) return;
    
    const query = input.value.toLowerCase().trim();
    if(query === '') return;

    for(const course of courses) {
        for(const keyword of course.keywords) {
            if(query.includes(keyword.toLowerCase())) {
                window.location.href = course.url;
                return;
            }
        }
    }

    alert('دوره‌ای با این نام پیدا نشد!');
}

const themeToggle = document.getElementById('shab');
if(themeToggle) {
    themeToggle.addEventListener('click', function() {
        document.body.classList.toggle('light');
        if(document.body.classList.contains('light')) {
            localStorage.setItem('theme', 'light');
            themeToggle.textContent = 'حالت تاریک';
        } else {
            localStorage.setItem('theme', 'dark');
            themeToggle.textContent = 'حالت روشن';
        }
    });

    if(localStorage.getItem('theme') === 'light') {
        themeToggle.textContent = 'حالت تاریک';
    }else{
        themeToggle.textContent = "حالت روشن"   
     }
}

const listes = document.querySelector(".listes");

const panel = document.getElementById('vro');
if(panel) {
    panel.addEventListener("click", function(e){
        e.stopPropagation();
        listes.classList.toggle('open');
    });
    
    document.addEventListener("click", function(){
        listes.classList.remove('open');
    });
}

async function checkUser() {

    const { data, error } = await window.db.auth.getSession();

    if(error) {
        console.log(error);
        return;
    }

    const loginText = document.querySelector(".login-text");
    const profileMenu = document.querySelector(".listes");

    if(!loginText) return;

    if(data.session) {

        loginText.textContent = "پروفایل";

        const profileBtn = document.getElementById("vro");

        if(profileBtn) {
            profileBtn.onclick = function(e) {

                e.preventDefault();

                if(profileMenu) {
                    profileMenu.classList.toggle("open");
                }

            };
        }

    } else {

        loginText.textContent = "ثبت نام/ورود";

        const profileBtn = document.getElementById("vro");

        if(profileBtn) {
            profileBtn.onclick = function() {
                window.location.href = "login.html";
            };
        }
    }
}

checkUser();