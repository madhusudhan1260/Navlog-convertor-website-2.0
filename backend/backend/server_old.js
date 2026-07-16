require("dotenv").config();

const express = require("express");
const cors = require("cors");
const multer = require("multer");
const fs = require("fs");
const path = require("path");

const parseHTML = require("./htmlParser");
const convertWithClaude = require("./claude");
const generatePDF = require("./pdfGenerator");

const app = express();

const PORT = process.env.PORT || 5000;

const PUBLIC_URL =
process.env.PUBLIC_BASE_URL ||
`http://localhost:${PORT}`;


// ================= APP =================

app.use(cors());

app.use(express.json());

app.use(express.urlencoded({extended:true}));

app.use(
"/generated",
express.static(
path.join(__dirname,"generated")
)
);




// ================= MULTER =================

const upload = multer({

dest:path.join(
__dirname,
"uploads"
)

});




// ================= TEST =================

app.get("/",(req,res)=>{

res.send(
"🚀 EFLIGHT AI Backend Running"
);

});




// ================= EMPTY ROUTE =================

function emptyRoute(){

return{

header:"",

performance:{},

fuel:{},

weight:{},

route:"",

waypoints:[],

airportInfo:{}

};

}




// ================= READ HTML =================

function readHTML(file,label){

if(!file){

console.log(
`${label} not uploaded`
);

return null;

}

const html = fs.readFileSync(
file.path,
"utf8"
);

console.log(
`${label} HTML Size:`,
html.length
);

const parsed =
parseHTML(html);

console.log(
`\n========= ${label} PARSED =========`
);

console.log(
JSON.stringify(parsed,null,2)
);

return parsed;

}
app.post(

"/convert",

upload.fields([

{

name:"mainHtml",

maxCount:1

},

{

name:"alternate1Html",

maxCount:1

},

{

name:"alternate2Html",

maxCount:1

}

]),

async(req,res)=>{

try{

console.log(
"\n================ NEW CONVERSION ================"
);



// ================= USER INPUT =================

const userInput={

callSign:req.body.callSign,

pilotName:req.body.pilotName,

coPilotName:req.body.coPilotName,

departure:req.body.departure,

destination:req.body.destination,

paxWeight:req.body.paxWeight,

maxTripFuel:req.body.maxTripFuel,

endurance:req.body.endurance,

flightLevel:req.body.flightLevel,

shortFPL:req.body.shortFPL,

selectedFormat:req.body.selectedFormat

};



console.log(
"\n========= USER INPUT ========="
);

console.log(
JSON.stringify(userInput,null,2)
);




// ================= READ HTML FILES =================

const files = req.files || {};

const mainRoute =
  readHTML(
    files.mainHtml ? files.mainHtml[0] : null,
    "MAIN ROUTE"
  ) || emptyRoute();

const alternate1 =
  readHTML(
    files.alternate1Html ? files.alternate1Html[0] : null,
    "ALTERNATE 1"
  ) || emptyRoute();

const alternate2 =
  readHTML(
    files.alternate2Html ? files.alternate2Html[0] : null,
    "ALTERNATE 2"
  ) || emptyRoute();



const alternate1 =

readHTML(

req.files.alternate1Html
?req.files.alternate1Html[0]
:null,

"ALTERNATE 1"

) || emptyRoute();



const alternate2 =

readHTML(

req.files.alternate2Html
?req.files.alternate2Html[0]
:null,

"ALTERNATE 2"

) || emptyRoute();




// ================= DELETE TEMP FILES =================

Object.values(req.files || {}).forEach(arr=>{

arr.forEach(file=>{

try{

fs.unlinkSync(file.path);

}

catch(e){}

});

});




// ================= MASTER JSON =================

const masterJson={

userInput,

mainRoute,

alternate1,

alternate2

};



console.log(
"\n========= MASTER JSON ========="
);

console.log(
JSON.stringify(masterJson,null,2)
);




// ================= CLAUDE =================

const finalJson=

await convertWithClaude(masterJson);



console.log(
"\n========= CLAUDE OUTPUT ========="
);

console.log(
JSON.stringify(finalJson,null,2)
);




// ================= PDF =================

const pdfPath=

await generatePDF(finalJson);



console.log(
"\n✅ PDF CREATED:"
);

console.log(pdfPath);




// ================= RESPONSE =================

res.json({

success:true,

pdf:

`${PUBLIC_URL}/`+

pdfPath.replaceAll(

path.sep,

"/"

),

data:finalJson

});


}

catch(error){

console.log(error);

res.status(500).json({

success:false,

message:error.message

});

}

}

);
app.listen(PORT,()=>{

console.log(
`🚀 Backend running at ${PUBLIC_URL}`
);

});

module.exports = app;