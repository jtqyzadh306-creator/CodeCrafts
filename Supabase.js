const supabaseUrl = "https://qftowgewgcbpocqvlvpm.supabase.co";
const supabaseKey = "sb_publishable_-Z_jxxQk2Riv4EJustk2Gg_4yBy0Xtt";

window.db = window.supabase.createClient(
    supabaseUrl,
    supabaseKey
);

console.log(window.db);










