import { useState } from "react";
import { useNavigate } from "react-router-dom";


function Login(){


const navigate = useNavigate();


const [email,setEmail] = useState("");

const [password,setPassword] = useState("");

const [error,setError] = useState("");



const handleLogin = () =>{


setError("");


// empty check

if(email === "" || password === ""){


setError("⚠️ Enter username and password");

return;

}



// eflight mail check

if(!email.endsWith("@eflight.com")){


setError("🚫 Only @eflight.com users allowed");

return;

}



// already registered user check

const savedPassword = localStorage.getItem(email);



if(savedPassword){



if(savedPassword === password){


navigate("/dashboard");


}

else{


setError("❌ Wrong Password");

}



}


// first login save password

else{


localStorage.setItem(
email,
password
);


navigate("/dashboard");


}



}




return(

<div className="login-bg">


<div className="login-card">


<div className="plane">

✈️

</div>



<h1>

EFLIGHT AI

</h1>



<h3>

Navlog Converter System

</h3>



<p>

Secure Aviation Login Portal

</p>




<input

placeholder="Enter EFlight Email"

value={email}

onChange={(e)=>setEmail(e.target.value)}

/>



<input

placeholder="Enter Password"

type="password"

value={password}

onChange={(e)=>setPassword(e.target.value)}

/>




{

error &&

<div className="error">

{error}

</div>

}



<button onClick={handleLogin}>

LOGIN

</button>



</div>



</div>


)


}


export default Login;